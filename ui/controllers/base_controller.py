import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import flet as ft

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


@dataclass(frozen=True)
class JobUI:
    """UI handles a controller needs to report progress for one tool page."""

    page: ft.Page
    lbl_status: ft.Text
    progress_bar: ft.ProgressBar
    btn_action: ft.ElevatedButton


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
    ) -> None:
        """Opens file or directory picker preventing concurrent window spawns and non-existent paths.

        Args:
            picker: The Flet FilePicker component instance.
            allow_directory: Flag indicating whether to pick directories instead of files.
            is_output: Flag indicating whether this picker handles destination directory selection.
            allowed_extensions: Optional list of allowed file extension strings without leading dot.
        """
        if not self.picker_active:
            self.picker_active = True
            target_path = self.selected_output_dir if is_output else self.selected_input
            safe_dir = get_safe_initial_directory(target_path)

            if allow_directory:
                picker.get_directory_path(initial_directory=safe_dir)
            else:
                picker.pick_files(
                    allow_multiple=False,
                    initial_directory=safe_dir,
                    allowed_extensions=allowed_extensions,
                )

    def handle_input_result(
        self,
        e: ft.FilePickerResultEvent,
        lbl_path: ft.Text,
        lbl_status: ft.Text | None = None,
    ) -> None:
        """Handles selection result from input file or directory picker."""
        self.picker_active = False
        if e.files and len(e.files) > 0:
            self.selected_input = Path(e.files[0].path)
        elif e.path:
            self.selected_input = Path(e.path)

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
        if e.path:
            self.selected_output_dir = Path(e.path)
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
        page.session.set("is_processing", processing)
        back_row = page.session.get("back_row")
        if back_row is not None:
            back_row.visible = not processing
            back_row.update()

    def _set_processing_ui(
        self,
        page: ft.Page,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Transitions UI controls and session flags to active processing state."""
        self._set_processing_state(page, True)

        progress_bar.value = None
        progress_bar.visible = True
        progress_bar.update()

        btn_action.text = t("btn_stop_process")
        btn_action.icon = ft.icons.STOP
        btn_action.bgcolor = get_color("danger")
        btn_action.color = "#FFFFFF"
        btn_action.update()

    def _restore_idle_ui(
        self,
        page: ft.Page,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Restores UI controls and session flags back to idle ready state."""
        self._set_processing_state(page, False)

        progress_bar.visible = False
        progress_bar.update()

        btn_action.text = t("btn_process")
        btn_action.icon = ft.icons.PLAY_ARROW
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
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Displays modal dialog asking user confirmation to abort running operation."""

        def on_keep_running(_: ft.ControlEvent) -> None:
            self._close_cancel_dialog(page)

        def on_stop_confirmed(_: ft.ControlEvent) -> None:
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
            actions=[
                ft.TextButton(t("btn_keep_running"), on_click=on_keep_running),
                ft.ElevatedButton(
                    t("btn_stop_and_delete"),
                    bgcolor=get_color("danger"),
                    color="#FFFFFF",
                    on_click=on_stop_confirmed,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.dialog = self.cancel_dialog
        self.cancel_dialog.open = True
        page.update()

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
    ) -> bool:
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
    def _summary_counts(summary: dict[str, Any]) -> tuple[int, int]:
        """Normalizes (success, total) across the different engine summary shapes."""
        success = summary.get("success", summary.get("successful", 0))
        total = summary.get("total_files", summary.get("total"))
        if total is None:
            total = success + summary.get("failed", 0)
        return success, total

    def _run_single_file_job(self, ui: JobUI, params: Any) -> None:
        """Template for a single-file job: lifecycle, metrics, cancellation and summary dialog."""
        input_path = self.selected_input
        output_dir = self.selected_output_dir
        if not input_path or not output_dir:
            return

        filename = input_path.name
        out_file = self.build_output_path(input_path, output_dir, params)
        pre_existed = out_file.exists()

        self._set_processing_ui(ui.page, ui.progress_bar, ui.btn_action)
        self.cancel_event.clear()

        try:
            self._set_status(
                ui.lbl_status, self._progress_text(1, 1, filename), "text"
            )

            orig_bytes = input_path.stat().st_size
            start_time = time.time()
            success = False

            redirector = TextRedirector()
            redirector.start()

            def file_progress_cb(
                duration: float, processed: float, fps: float, speed: float
            ) -> None:
                if self.abort_requested:
                    return
                if duration > 0.0:
                    ui.progress_bar.value = min(1.0, max(0.0, processed / duration))
                    ui.progress_bar.update()
                ui.lbl_status.value = self._progress_text(1, 1, filename, speed, fps)
                ui.lbl_status.update()

            try:
                success = self.run_single_engine(
                    input_path, out_file, params, file_progress_cb
                )
                print(f"[OK] {filename}" if success else f"[FAIL] {filename}")
            except InterruptedError:
                success = False
                self.abort_requested = True
                print(f"[CANCELLED] {filename}")
            except Exception as err:
                success = False
                print(f"[ERROR] {filename}: {err}")
            finally:
                redirector.stop()

            elapsed = time.time() - start_time
            comp_bytes = out_file.stat().st_size if success and out_file.exists() else 0

            self._close_cancel_dialog(ui.page)

            if not self.abort_requested:
                self._set_status(
                    ui.lbl_status,
                    t("msg_success" if success else "msg_error"),
                    "success" if success else "error",
                )
                show_summary_dialog(
                    ui.page,
                    {
                        "total_files": 1,
                        "success": 1 if success else 0,
                        "failed": 0 if success else 1,
                        "elapsed_seconds": round(elapsed, 2),
                        "original_bytes": orig_bytes,
                        "compressed_bytes": comp_bytes,
                        "terminal_log": redirector.get_logs(),
                        "errors": []
                        if success
                        else [{"file": filename, "error": t("msg_error")}],
                    },
                )
            else:
                if not pre_existed and out_file.exists():
                    try:
                        out_file.unlink()
                    except OSError:
                        pass
                self._set_status(
                    ui.lbl_status, t("msg_process_cancelled", count=1), "error"
                )
        finally:
            self._restore_idle_ui(ui.page, ui.progress_bar, ui.btn_action)

    def _run_batch_directory_job(self, ui: JobUI, params: Any) -> None:
        """Template for a folder job: progress, cancellation, error/no_files handling, summary dialog."""
        input_dir = self.selected_input
        output_dir = self.selected_output_dir
        if not input_dir or not output_dir:
            return

        self._set_processing_ui(ui.page, ui.progress_bar, ui.btn_action)
        self.cancel_event.clear()
        ui.progress_bar.value = 0
        ui.progress_bar.update()

        def update_progress(info: ProgressInfo) -> None:
            if self.abort_requested or self.cancel_event.is_set():
                raise InterruptedError("CANCELLED_BY_USER")

            if info.total > 0:
                ui.progress_bar.value = info.percentage / 100.0
                file_name = info.file_path.name if info.file_path else ""

                if info.is_completed:
                    print(f"[OK] {file_name}" if info.success else f"[FAIL] {file_name}")

                ui.lbl_status.value = self._progress_text(
                    info.current,
                    info.total,
                    file_name,
                    getattr(info, "speed", 0.0),
                    getattr(info, "fps", 0.0),
                )
                ui.progress_bar.update()
                ui.lbl_status.update()

        redirector = TextRedirector()
        redirector.start()

        summary: dict[str, Any] = {}
        try:
            summary = self.run_batch_engine(input_dir, output_dir, params, update_progress)

            if summary.get("cancelled", False):
                self.abort_requested = True

            self._close_cancel_dialog(ui.page)

            if not self.abort_requested:
                if summary.get("error"):
                    # Batch-level failure reported by the engine: show it as an
                    # error, never as success. The finally block restores the UI.
                    logger.error(
                        f"Batch processing returned an error: {summary['error']}"
                    )
                    self._set_status(ui.lbl_status, t("msg_error"), "error")
                    return

                if summary.get("no_files", False):
                    self._set_status(ui.lbl_status, "")
                    show_no_supported_files_dialog(ui.page, self.supported_formats())
                    return

                ui.progress_bar.value = 1.0
                ui.progress_bar.update()

                success_cnt, total_cnt = self._summary_counts(summary)
                self._set_status(
                    ui.lbl_status,
                    t(
                        "msg_success_summary",
                        msg=t("msg_success"),
                        successful=success_cnt,
                        total=total_cnt,
                    ),
                    "success",
                )

                summary["terminal_log"] = redirector.get_logs()
                show_summary_dialog(ui.page, summary)

        except InterruptedError as err:
            self.abort_requested = True
            print(f"[FAIL] {err}")

        except Exception as err:
            logger.exception("Batch processing failed unexpectedly")
            print(f"[ERROR] {err}")
            self._set_status(ui.lbl_status, t("msg_error"), "error")

        finally:
            redirector.stop()
            self._close_cancel_dialog(ui.page)

            if self.abort_requested:
                cleaned_count = summary.get("cleaned_files_count", 0)
                self._set_status(
                    ui.lbl_status,
                    t("msg_process_cancelled", count=cleaned_count),
                    "error",
                )

            self._restore_idle_ui(ui.page, ui.progress_bar, ui.btn_action)
