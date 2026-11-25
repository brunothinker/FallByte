import inspect
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import flet as ft

from src.utils.file_result import FileResult, LogLevel, as_file_result
from src.utils.progress import ProgressInfo
from ui.components.dialog_utils import (
    show_no_supported_files_dialog,
    show_summary_dialog,
)
from ui.components.incompatible_dialog import show_incompatible_files_dialog
from ui.i18n import t
from ui.theme import get_color
from ui.utils.log_capture import TextRedirector
from ui.utils.path_utils import get_safe_initial_directory

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, float, float, float], None]


def _schedule_on_page(page: ft.Page, fn: Callable[[], None]) -> None:
    """Runs a UI mutation safely on the page event loop (with test-mock fallback)."""
    run_task = getattr(page, "run_task", None)
    if callable(run_task):
        async def _runner() -> None:
            fn()

        res = run_task(_runner)
        # If page is a MagicMock in unit tests, run_task returns a MagicMock instead of a Future.
        if not hasattr(res, "done") and not inspect.isawaitable(res):
            fn()
        return
    fn()


@dataclass(frozen=True)
class JobUI:
    """UI handles a controller needs to report progress for one tool page."""

    page: ft.Page
    lbl_status: ft.Text
    progress_bar: ft.ProgressBar
    btn_action: ft.Button


class BaseController:
    """Base controller: shared state, picker handlers, UI transitions and job templates.

    Concrete controllers only describe *what* to run through hooks:

    * ``progress_i18n_key`` / ``show_speed`` / ``show_fps`` (class attributes)
    * ``supported_formats()``
    * ``build_output_path(...)`` and ``run_single_engine(...)`` for single-file jobs
    * ``run_batch_engine(...)`` for folder jobs
    * optional ``validate_params(...)`` and ``preflight_batch(...)``

    The lifecycle (redirector, timing, byte metrics, cancellation, error handling,
    status label, summary dialog, idle UI restore) lives here, in
    ``_run_single_file_job`` and ``_run_batch_directory_job``.
    """

    # i18n key used for the "[current/total] - filename" status line.
    progress_i18n_key: str = "msg_converting_progress"
    # Append " (1.2x)" / " (1.2x, 30 fps)" to the status line when engines report it.
    show_speed: bool = False
    show_fps: bool = False
    # Which input kinds the tool accepts.
    supports_single_file: bool = True
    supports_batch_directory: bool = True
    # i18n key shown when the selected input kind is not supported.
    invalid_input_key: str = "msg_select_required"

    def __init__(self) -> None:
        """Initializes state variables shared across UI controllers."""
        self.selected_input: Path | None = None
        self.selected_output_dir: Path | None = None
        self.is_processing: bool = False
        self.abort_requested: bool = False
        self.picker_active: bool = False
        self.cancel_dialog: ft.AlertDialog | None = None
        self.cancel_event: threading.Event = threading.Event()

    # ------------------------------------------------------------------
    # Path validation and pickers
    # ------------------------------------------------------------------

    def validate_paths(self) -> str | None:
        """Validates source and destination paths to prevent overwriting or nested recursion.

        Returns:
            str | None: i18n translation key string if validation fails, otherwise None.
        """
        if not self.selected_input or not self.selected_output_dir:
            return "msg_select_required"

        src = self.selected_input.resolve()
        dst = self.selected_output_dir.resolve()

        if src.is_file():
            if src.parent == dst:
                return "msg_same_folder_error"
            if dst in src.parents:
                return "msg_nested_folder_error"
        else:
            if src == dst:
                return "msg_same_folder_error"
            if dst in src.parents or src in dst.parents:
                return "msg_nested_folder_error"

        return None

    def open_picker(
        self,
        picker: ft.FilePicker,
        allow_directory: bool = False,
        is_output: bool = False,
        allowed_extensions: list[str] | None = None,
        page: ft.Page | None = None,
        on_result: Callable[[ft.FilePickerResultEvent], None] | None = None,
    ) -> None:
        """Opens file or directory picker preventing concurrent window spawns and non-existent paths."""
        if self.picker_active:
            return

        self.picker_active = True
        target_path = self.selected_output_dir if is_output else self.selected_input
        safe_dir = get_safe_initial_directory(target_path)
        active_page = page or getattr(picker, "page", None)
        result_cb = on_result or getattr(picker, "on_result", None)

        async def _pick_async() -> None:
            try:
                if allow_directory:
                    selected_dir = await picker.get_directory_path(
                        initial_directory=safe_dir
                    )
                    files = (
                        [
                            ft.FilePickerFile(
                                id=0,
                                name=Path(selected_dir).name or selected_dir,
                                size=0,
                                path=selected_dir,
                            )
                        ]
                        if selected_dir
                        else []
                    )
                    if callable(result_cb):
                        result_cb(
                            ft.FilePickerResultEvent(
                                name="result",
                                control=picker,
                                files=files,
                            )
                        )
                else:
                    picked_files = await picker.pick_files(
                        allow_multiple=False,
                        initial_directory=safe_dir,
                        allowed_extensions=allowed_extensions,
                    )
                    if callable(result_cb):
                        result_cb(
                            ft.FilePickerResultEvent(
                                name="result",
                                control=picker,
                                files=picked_files or [],
                            )
                        )
            finally:
                self.picker_active = False

        is_async_picker = inspect.iscoroutinefunction(
            getattr(picker, "get_directory_path" if allow_directory else "pick_files", None)
        )
        if is_async_picker and active_page is not None and callable(getattr(active_page, "run_task", None)):
            active_page.run_task(_pick_async)
        else:
            # Fallback for unit tests calling open_picker with a mocked picker directly.
            if allow_directory:
                res = picker.get_directory_path(initial_directory=safe_dir)
            else:
                res = picker.pick_files(
                    allow_multiple=False,
                    initial_directory=safe_dir,
                    allowed_extensions=allowed_extensions,
                )
            if inspect.iscoroutine(res):
                res.close()

    @staticmethod
    def _extract_picked_path(e: ft.FilePickerResultEvent) -> str | None:
        files = getattr(e, "files", None)
        if files and len(files) > 0 and getattr(files[0], "path", None):
            return files[0].path
        return getattr(e, "path", None)

    def handle_input_result(
        self,
        e: ft.FilePickerResultEvent,
        lbl_path: ft.Text,
        lbl_status: ft.Text | None = None,
    ) -> None:
        """Handles selection result from input file or directory picker."""
        self.picker_active = False
        picked = self._extract_picked_path(e)
        if picked:
            self.selected_input = Path(picked)

        if self.selected_input:
            lbl_path.value = self.selected_input.name or str(self.selected_input)
            lbl_path.color = get_color("text")
            lbl_path.update()

            if lbl_status:
                lbl_status.value = ""
                lbl_status.update()

    def handle_output_result(
        self,
        e: ft.FilePickerResultEvent,
        lbl_path: ft.Text,
        lbl_status: ft.Text | None = None,
    ) -> None:
        """Handles selection result from output directory picker."""
        self.picker_active = False
        picked = self._extract_picked_path(e)
        if picked:
            self.selected_output_dir = Path(picked)
            lbl_path.value = self.selected_output_dir.name or str(
                self.selected_output_dir
            )
            lbl_path.color = get_color("text")
            lbl_path.update()

            if lbl_status:
                lbl_status.value = ""
                lbl_status.update()

    # ------------------------------------------------------------------
    # UI state transitions
    # ------------------------------------------------------------------

    def _set_processing_state(self, page: ft.Page, processing: bool) -> None:
        """Keep the navigation lock and the layout's Back row in sync."""
        self.is_processing = processing
        self.abort_requested = False
        if not isinstance(getattr(page, "data", None), dict):
            page.data = {}
        page.data["is_processing"] = processing
        back_row = page.data.get("back_row")
        if back_row is not None:
            back_row.visible = not processing
            back_row.update()

    def _set_processing_ui(
        self,
        page: ft.Page,
        progress_bar: ft.ProgressBar,
        btn_action: ft.Button,
    ) -> None:
        """Transitions UI controls and page state flags to active processing state."""
        self._set_processing_state(page, True)

        progress_bar.value = None
        progress_bar.visible = True
        progress_bar.update()

        btn_action.content = t("btn_stop_process")
        btn_action.icon = ft.Icons.STOP
        btn_action.bgcolor = get_color("danger")
        btn_action.color = "#FFFFFF"
        btn_action.update()

    def _restore_idle_ui(
        self,
        page: ft.Page,
        progress_bar: ft.ProgressBar,
        btn_action: ft.Button,
    ) -> None:
        """Restores UI controls and page state flags back to idle ready state."""
        self._set_processing_state(page, False)

        progress_bar.visible = False
        progress_bar.update()

        btn_action.content = t("btn_process")
        btn_action.icon = ft.Icons.PLAY_ARROW
        btn_action.bgcolor = get_color("primary")
        btn_action.color = get_color("text")
        btn_action.update()

    @staticmethod
    def _set_status(lbl_status: ft.Text, text: str, color_key: str | None = None) -> None:
        """Updates the status label text and, optionally, its theme color."""
        lbl_status.value = text
        if color_key is not None:
            lbl_status.color = get_color(color_key)
        lbl_status.update()

    def _close_cancel_dialog(self, page: ft.Page) -> None:
        """Closes and unmounts active processing cancellation dialog."""
        if self.cancel_dialog:
            self.cancel_dialog.open = False
            page.pop_dialog()
            page.update()
            self.cancel_dialog = None

    def _on_cancel_confirmed(self) -> None:
        """Signals the cancellation event shared by all running jobs."""
        self.cancel_event.set()

    def _confirm_cancel_process(
        self,
        page: ft.Page,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.Button,
    ) -> None:
        """Displays modal dialog asking user confirmation to abort running operation."""

        def on_keep_running(_: Any) -> None:
            self._close_cancel_dialog(page)

        def on_stop_confirmed(_: Any) -> None:
            self.abort_requested = True
            self._on_cancel_confirmed()
            self._close_cancel_dialog(page)

            lbl_status.value = t("msg_cancelling")
            lbl_status.color = get_color("warning")
            lbl_status.update()

        self.cancel_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(t("dialog_cancel_title")),
            content=ft.Text(t("dialog_cancel_body")),
            actions=list[ft.Control]([
                ft.TextButton(content=t("btn_keep_running"), on_click=on_keep_running),
                ft.Button(
                    content=t("btn_stop_and_delete"),
                    bgcolor=get_color("danger"),
                    color="#FFFFFF",
                    on_click=on_stop_confirmed,
                ),
            ]),
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.show_dialog(self.cancel_dialog)

    # ------------------------------------------------------------------
    # Hooks implemented by concrete controllers
    # ------------------------------------------------------------------

    def supported_formats(self) -> list[str]:
        """Upper-case format names accepted by the tool (for the 'no supported files' dialog)."""
        return []

    def validate_params(self, params: Any) -> str | None:
        """Returns an i18n error key when the tool parameters are invalid, otherwise None."""
        return None

    def build_output_path(self, input_path: Path, output_dir: Path, params: Any) -> Path:
        """Computes the collision-free output path for a single-file job."""
        raise NotImplementedError

    def run_single_engine(
        self,
        input_path: Path,
        output_path: Path,
        params: Any,
        progress_cb: ProgressCallback,
    ) -> FileResult:
        """Runs the single-file engine. ``progress_cb(duration, processed, fps, speed)`` is optional to use."""
        raise NotImplementedError

    def run_batch_engine(
        self,
        input_dir: Path,
        output_dir: Path,
        params: Any,
        progress_callback: Callable[[ProgressInfo], None],
    ) -> dict[str, Any]:
        """Runs the batch engine and returns its summary dictionary."""
        raise NotImplementedError

    def preflight_batch(
        self, ui: JobUI, params: Any, proceed: Callable[[], None]
    ) -> None:
        """Hook run on the UI thread before a batch job. Call ``proceed()`` to start it."""
        proceed()

    def _preflight_by_support(
        self,
        ui: JobUI,
        proceed: Callable[[], None],
        is_supported: Callable[[Path], bool],
    ) -> None:
        """Scans the input folder and asks for confirmation when unsupported files are present."""
        root = self.selected_input
        if not root:
            return

        supported: list[Path] = []
        unsupported: list[Path] = []
        for f in root.rglob("*"):
            if f.is_file():
                (supported if is_supported(f) else unsupported).append(f)

        if not supported:
            self._set_status(ui.lbl_status, "")
            show_no_supported_files_dialog(ui.page, self.supported_formats())
            return

        if unsupported:
            show_incompatible_files_dialog(
                ui.page,
                unsupported_files=unsupported,
                supported_count=len(supported),
                on_confirm=proceed,
            )
            return

        proceed()

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------

    def execute(self, ui: JobUI, params: Any = None) -> None:
        """Uniform entrypoint: starts the job or asks to cancel the running one."""
        if self.is_processing:
            self._confirm_cancel_process(
                ui.page, ui.lbl_status, ui.progress_bar, ui.btn_action
            )
            return

        error_key = self.validate_paths()
        if error_key or not self.selected_input:
            self._set_status(ui.lbl_status, t(error_key or "msg_select_required"), "error")
            return

        params_error = self.validate_params(params)
        if params_error:
            self._set_status(ui.lbl_status, t(params_error), "error")
            return

        is_file = self.selected_input.is_file()
        if (is_file and not self.supports_single_file) or (
            not is_file and not self.supports_batch_directory
        ):
            self._set_status(ui.lbl_status, t(self.invalid_input_key), "error")
            return

        if is_file:
            self._start_thread(self._run_single_file_job, ui, params)
        else:
            self.preflight_batch(
                ui,
                params,
                lambda: self._start_thread(self._run_batch_directory_job, ui, params),
            )

    @staticmethod
    def _start_thread(target: Callable[..., None], *args: Any) -> None:
        threading.Thread(target=target, args=args, daemon=True).start()

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------

    def _speed_suffix(self, speed: float, fps: float) -> str:
        if not self.show_speed or speed <= 0.0:
            return ""
        if self.show_fps:
            return f" ({speed:.1f}x, {fps:.0f} fps)"
        return f" ({speed:.1f}x)"

    def _progress_text(
        self,
        current: int,
        total: int,
        filename: str,
        speed: float = 0.0,
        fps: float = 0.0,
    ) -> str:
        text = t(
            self.progress_i18n_key, current=current, total=total, filename=filename
        )
        return text + self._speed_suffix(speed, fps)

    @staticmethod
    def _format_result_entry(
        filename: str,
        result: FileResult,
    ) -> tuple[LogLevel, str]:
        """Formats a single-file outcome into a (LogLevel, line) pair without text sniffing."""
        if result.is_skipped:
            reason = (
                t(result.reason_key, **result.reason_params)
                if result.reason_key
                else ""
            )
            msg = f"[SKIP] {filename} - {reason}" if reason else f"[SKIP] {filename}"
            return result.log_level, msg
        if result.is_processed:
            return result.log_level, f"[OK] {filename}"
        return result.log_level, f"[FAIL] {filename}"

    @staticmethod
    def _summary_counts(summary: dict[str, Any]) -> tuple[int, int, int, int]:
        """Normalizes (success, skipped, failed, total) across engine summary shapes."""
        success = summary.get("success", summary.get("successful", 0))
        skipped = summary.get("skipped", 0)
        failed = summary.get("failed", 0)
        total = summary.get("total_files", summary.get("total"))
        if total is None:
            total = success + skipped + failed
        return success, skipped, failed, total

    def _run_single_file_job(self, ui: JobUI, params: Any) -> None:
        """Template for a single-file job: lifecycle, metrics, cancellation and summary dialog."""
        input_path = self.selected_input
        output_dir = self.selected_output_dir
        if not input_path or not output_dir:
            return

        filename = input_path.name
        out_file = self.build_output_path(input_path, output_dir, params)
        pre_existed = out_file.exists()

        _schedule_on_page(
            ui.page,
            lambda: self._set_processing_ui(ui.page, ui.progress_bar, ui.btn_action),
        )
        self.cancel_event.clear()

        try:
            _schedule_on_page(
                ui.page,
                lambda: self._set_status(
                    ui.lbl_status, self._progress_text(1, 1, filename), "text"
                ),
            )

            orig_bytes = input_path.stat().st_size
            start_time = time.time()
            result = FileResult.failed()

            redirector = TextRedirector()
            redirector.start()

            def file_progress_cb(
                duration: float, processed: float, fps: float, speed: float
            ) -> None:
                if self.abort_requested:
                    return

                def _apply_progress() -> None:
                    if duration > 0.0:
                        ui.progress_bar.value = min(1.0, max(0.0, processed / duration))
                        ui.progress_bar.update()
                    ui.lbl_status.value = self._progress_text(1, 1, filename, speed, fps)
                    ui.lbl_status.update()

                _schedule_on_page(ui.page, _apply_progress)

            try:
                result = as_file_result(
                    self.run_single_engine(
                        input_path, out_file, params, file_progress_cb
                    )
                )
                level, line = self._format_result_entry(filename, result)
                redirector.log(level, line)
            except InterruptedError:
                result = FileResult.failed()
                self.abort_requested = True
                redirector.log(LogLevel.WARNING, f"[CANCELLED] {filename}")
            except Exception as err:
                result = FileResult.failed()
                redirector.log(LogLevel.ERROR, f"[ERROR] {filename}: {err}")
            finally:
                redirector.stop()

            elapsed = time.time() - start_time
            comp_bytes = (
                out_file.stat().st_size
                if result.is_processed and out_file.exists()
                else 0
            )

            _schedule_on_page(ui.page, lambda: self._close_cancel_dialog(ui.page))

            if not self.abort_requested:
                if result.is_processed:
                    status_key = "msg_success"
                    status_color = "success"
                elif result.is_skipped:
                    status_key = "msg_kept_original"
                    status_color = "warning"
                else:
                    status_key = "msg_error"
                    status_color = "error"

                summary_payload = {
                    "total_files": 1,
                    "success": 1 if result.is_processed else 0,
                    "skipped": 1 if result.is_skipped else 0,
                    "failed": 1 if result.is_failed else 0,
                    "elapsed_seconds": round(elapsed, 2),
                    "original_bytes": orig_bytes if result.is_processed else 0,
                    "compressed_bytes": comp_bytes,
                    "terminal_log": redirector.get_logs(),
                    "log_entries": redirector.get_entries(),
                    "errors": [{"file": filename, "error": t("msg_error")}]
                    if result.is_failed
                    else [],
                }

                def _finish_single_ui() -> None:
                    self._set_status(ui.lbl_status, t(status_key), status_color)
                    show_summary_dialog(ui.page, summary_payload)

                _schedule_on_page(ui.page, _finish_single_ui)
            else:
                if not pre_existed and out_file.exists():
                    try:
                        out_file.unlink()
                    except OSError:
                        pass
                _schedule_on_page(
                    ui.page,
                    lambda: self._set_status(
                        ui.lbl_status, t("msg_process_cancelled", count=1), "error"
                    ),
                )
        finally:
            _schedule_on_page(
                ui.page,
                lambda: self._restore_idle_ui(ui.page, ui.progress_bar, ui.btn_action),
            )

    def _run_batch_directory_job(self, ui: JobUI, params: Any) -> None:
        """Template for a folder job: progress, cancellation, error/no_files handling, summary dialog."""
        input_dir = self.selected_input
        output_dir = self.selected_output_dir
        if not input_dir or not output_dir:
            return

        def _init_batch_ui() -> None:
            self._set_processing_ui(ui.page, ui.progress_bar, ui.btn_action)
            ui.progress_bar.value = 0
            ui.progress_bar.update()

        _schedule_on_page(ui.page, _init_batch_ui)
        self.cancel_event.clear()

        redirector = TextRedirector()

        def update_progress(info: ProgressInfo) -> None:
            if self.abort_requested or self.cancel_event.is_set():
                raise InterruptedError("CANCELLED_BY_USER")

            if info.total > 0:
                file_name = info.file_path.name if info.file_path else ""

                if info.is_completed:
                    if info.skipped:
                        file_res = FileResult.skipped(
                            info.skip_reason_key or "",
                            **(info.skip_reason_params or {}),
                        )
                    elif info.success:
                        file_res = FileResult.processed()
                    else:
                        file_res = FileResult.failed()

                    level, line = self._format_result_entry(file_name, file_res)
                    redirector.log(level, line)

                pct_val = info.percentage / 100.0
                status_text = self._progress_text(
                    info.current,
                    info.total,
                    file_name,
                    getattr(info, "speed", 0.0),
                    getattr(info, "fps", 0.0),
                )

                def _apply_batch_progress() -> None:
                    ui.progress_bar.value = pct_val
                    ui.lbl_status.value = status_text
                    ui.progress_bar.update()
                    ui.lbl_status.update()

                _schedule_on_page(ui.page, _apply_batch_progress)

        redirector.start()

        summary: dict[str, Any] = {}
        try:
            summary = self.run_batch_engine(input_dir, output_dir, params, update_progress)

            if summary.get("cancelled", False):
                self.abort_requested = True

            _schedule_on_page(ui.page, lambda: self._close_cancel_dialog(ui.page))

            if not self.abort_requested:
                if summary.get("error"):
                    logger.error(
                        f"Batch processing returned an error: {summary['error']}"
                    )
                    _schedule_on_page(
                        ui.page,
                        lambda: self._set_status(ui.lbl_status, t("msg_error"), "error"),
                    )
                    return

                if summary.get("no_files", False):
                    def _show_no_files() -> None:
                        self._set_status(ui.lbl_status, "")
                        show_no_supported_files_dialog(ui.page, self.supported_formats())

                    _schedule_on_page(ui.page, _show_no_files)
                    return

                success_cnt, skipped_cnt, failed_cnt, total_cnt = self._summary_counts(
                    summary
                )
                summary["terminal_log"] = redirector.get_logs()
                summary["log_entries"] = redirector.get_entries()

                def _finish_batch_ui() -> None:
                    ui.progress_bar.value = 1.0
                    ui.progress_bar.update()
                    self._set_status(
                        ui.lbl_status,
                        t(
                            "msg_batch_summary",
                            msg=t("msg_success"),
                            successful=success_cnt,
                            skipped=skipped_cnt,
                            failed=failed_cnt,
                            total=total_cnt,
                        ),
                        "success",
                    )
                    show_summary_dialog(ui.page, summary)

                _schedule_on_page(ui.page, _finish_batch_ui)

        except InterruptedError:
            self.abort_requested = True
            redirector.log(LogLevel.WARNING, f"[CANCELLED] {t('msg_cancelled_by_user')}")

        except Exception as err:
            logger.exception("Batch processing failed unexpectedly")
            redirector.log(LogLevel.ERROR, f"[ERROR] {err}")
            _schedule_on_page(
                ui.page,
                lambda: self._set_status(ui.lbl_status, t("msg_error"), "error"),
            )

        finally:
            redirector.stop()

            def _finalize_batch_ui() -> None:
                self._close_cancel_dialog(ui.page)
                if self.abort_requested:
                    cleaned_count = summary.get("cleaned_files_count", 0)
                    self._set_status(
                        ui.lbl_status,
                        t("msg_process_cancelled", count=cleaned_count),
                        "error",
                    )
                self._restore_idle_ui(ui.page, ui.progress_bar, ui.btn_action)

            _schedule_on_page(ui.page, _finalize_batch_ui)
