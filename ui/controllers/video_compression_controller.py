import threading
import time
from pathlib import Path

import flet as ft

from src.formats import SUPPORTED_VIDEO_EXTENSIONS
from src.utils.output_naming import unique_compression_output_path
from src.utils.progress import ProgressInfo
from src.video.video_directory_compression import directory_compressor
from src.video.video_file_compression import file_compressor
from ui.components.dialog_utils import (
    show_no_supported_files_dialog,
    show_summary_dialog,
)
from ui.controllers.base_controller import BaseController
from ui.i18n import t
from ui.theme import get_color
from ui.utils.format_utils import video_input_formats
from ui.utils.log_capture import TextRedirector


class VideoCompressionController(BaseController):
    """Controller managing single-file and batch directory video compression business logic."""

    def __init__(self) -> None:
        """Initializes state variables for video compression execution and safety guards."""
        super().__init__()
        self.cancel_event: threading.Event = threading.Event()

    def _on_cancel_confirmed(self) -> None:
        """Hook override triggering cancellation event for active video compression processes."""
        self.cancel_event.set()

    def handle_action_click(
        self,
        page: ft.Page,
        quality: int,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Routes trigger button click to execute process or request cancellation."""
        if self.is_processing:
            self._confirm_cancel_process(
                page, lbl_status, progress_bar, btn_action
            )
        else:
            self.prepare_and_execute(
                page, quality, lbl_status, progress_bar, btn_action
            )

    def prepare_and_execute(
        self,
        page: ft.Page,
        quality: int,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Analyzes input extensions and executes single-file or batch compression."""
        validation_error = self.validate_paths()
        if validation_error or not self.selected_input:
            lbl_status.value = t(validation_error or "msg_select_required")
            lbl_status.color = get_color("error")
            lbl_status.update()
            return

        if self.selected_input.is_file():
            threading.Thread(
                target=self._execute_single_file,
                args=(page, quality, lbl_status, progress_bar, btn_action),
                daemon=True,
            ).start()
        else:
            self._preflight_batch_execution(
                page, quality, lbl_status, progress_bar, btn_action
            )

    def _execute_single_file(
        self,
        page: ft.Page,
        quality: int,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Executes single-file video compression flow and displays summary dialog."""
        if not self.selected_input or not self.selected_output_dir:
            return

        filename = self.selected_input.name
        out_file = unique_compression_output_path(
            input_path=self.selected_input,
            output_dir=self.selected_output_dir,
        )
        pre_existed = out_file.exists()

        self._set_processing_ui(page, progress_bar, btn_action)
        self.cancel_event.clear()

        lbl_status.value = t(
            "msg_compressing_progress",
            current=1,
            total=1,
            filename=filename,
        )
        lbl_status.color = get_color("text")
        lbl_status.update()

        redirector = TextRedirector()
        redirector.start()

        start_time = time.time()
        orig_bytes = self.selected_input.stat().st_size
        success = False

        def file_progress_cb(
            duration: float, processed: float, fps: float, speed: float
        ) -> None:
            if self.abort_requested:
                return
            if duration > 0.0:
                pct = min(1.0, max(0.0, processed / duration))
                progress_bar.value = pct
                status_text = t(
                    "msg_compressing_progress",
                    current=1,
                    total=1,
                    filename=filename,
                )
                if speed > 0.0:
                    status_text += f" ({speed:.1f}x, {fps:.0f} fps)"
                lbl_status.value = status_text
                progress_bar.update()
                lbl_status.update()

        try:
            success = file_compressor(
                input_path=self.selected_input,
                output_path=out_file,
                quality=quality,
                cancel_event=self.cancel_event,
                file_progress_callback=file_progress_cb,
            )
            if success:
                print(f"[OK] {filename}")
            else:
                print(f"[FAIL] {filename}")
        except Exception as err:
            success = False
            print(f"[ERROR] {filename}: {err}")
        finally:
            redirector.stop()

        elapsed = time.time() - start_time
        comp_bytes = (
            out_file.stat().st_size if success and out_file.exists() else 0
        )

        self._close_cancel_dialog(page)

        if not self.abort_requested:
            if success:
                lbl_status.value = t("msg_success")
                lbl_status.color = get_color("success")
            else:
                lbl_status.value = t("msg_error")
                lbl_status.color = get_color("error")
            lbl_status.update()

            summary = {
                "total_files": 1,
                "success": 1 if success else 0,
                "failed": 0 if success else 1,
                "elapsed_seconds": round(elapsed, 2),
                "original_bytes": orig_bytes,
                "compressed_bytes": comp_bytes,
                "terminal_log": redirector.get_logs(),
                "errors": []
                if success
                else [
                    {
                        "file": filename,
                        "error": t("msg_error"),
                    }
                ],
            }
            show_summary_dialog(page, summary)
        else:
            if not pre_existed and out_file.exists():
                try:
                    out_file.unlink()
                except OSError:
                    pass
            lbl_status.value = t("msg_process_cancelled", count=1)
            lbl_status.color = get_color("error")
            lbl_status.update()

        self._restore_idle_ui(page, progress_bar, btn_action)

    def _preflight_batch_execution(
        self,
        page: ft.Page,
        quality: int,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Checks batch directory for unsupported extensions before execution."""
        if not self.selected_input:
            return

        all_files = [f for f in self.selected_input.rglob("*") if f.is_file()]
        supported_files: list[Path] = []
        unsupported_files: list[Path] = []

        for f in all_files:
            if f.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS:
                supported_files.append(f)
            else:
                unsupported_files.append(f)

        if len(supported_files) == 0:
            lbl_status.value = ""
            lbl_status.update()
            show_no_supported_files_dialog(page, video_input_formats())
            return

        if len(unsupported_files) > 0:
            ext_set = {f.suffix.upper() for f in unsupported_files if f.suffix}
            sample_exts = (
                ", ".join(list(ext_set)[:4])
                if ext_set
                else t("lbl_no_extension")
            )

            def close_dialog(_: ft.ControlEvent) -> None:
                dialog.open = False
                page.update()

            def confirm_and_run(_: ft.ControlEvent) -> None:
                dialog.open = False
                page.update()
                threading.Thread(
                    target=self._run_batch_compression,
                    args=(page, quality, lbl_status, progress_bar, btn_action),
                    daemon=True,
                ).start()

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text(
                    t("dialog_incompatible_title"), weight=ft.FontWeight.W_600
                ),
                content=ft.Text(
                    t(
                        "dialog_incompatible_body",
                        unsupported_count=len(unsupported_files),
                        supported_count=len(supported_files),
                        sample_exts=sample_exts,
                    ),
                    size=13,
                ),
                actions=[
                    ft.TextButton(t("btn_cancel"), on_click=close_dialog),
                    ft.ElevatedButton(
                        t("btn_continue"),
                        bgcolor=get_color("primary"),
                        color=get_color("text"),
                        on_click=confirm_and_run,
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            page.dialog = dialog
            dialog.open = True
            page.update()
        else:
            threading.Thread(
                target=self._run_batch_compression,
                args=(page, quality, lbl_status, progress_bar, btn_action),
                daemon=True,
            ).start()

    def _run_batch_compression(
        self,
        page: ft.Page,
        quality: int,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Executes batch directory video compression and updates progress indicators."""
        if not self.selected_input or not self.selected_output_dir:
            return

        self._set_processing_ui(page, progress_bar, btn_action)
        self.cancel_event.clear()
        progress_bar.value = 0
        progress_bar.update()

        def update_progress(info: ProgressInfo) -> None:
            if self.abort_requested:
                raise InterruptedError("CANCELLED_BY_USER")

            if info.total > 0:
                progress_bar.value = info.percentage / 100.0
                file_name = info.file_path.name if info.file_path else ""

                if info.is_completed:
                    if info.success:
                        print(f"[OK] {file_name}")
                    else:
                        print(f"[FAIL] {file_name}")

                status_text = t(
                    "msg_compressing_progress",
                    current=info.current,
                    total=info.total,
                    filename=file_name,
                )
                if info.speed > 0.0:
                    status_text += f" ({info.speed:.1f}x, {info.fps:.0f} fps)"

                lbl_status.value = status_text
                progress_bar.update()
                lbl_status.update()

        redirector = TextRedirector()
        redirector.start()

        summary = {}
        try:
            summary = directory_compressor(
                input_dir=self.selected_input,
                output_dir=self.selected_output_dir,
                quality=quality,
                progress_callback=update_progress,
                cancel_event=self.cancel_event,
            )

            if summary.get("cancelled", False):
                self.abort_requested = True

            self._close_cancel_dialog(page)

            if not self.abort_requested:
                if summary.get("no_files", False):
                    lbl_status.value = ""
                    lbl_status.update()
                    self._restore_idle_ui(page, progress_bar, btn_action)
                    show_no_supported_files_dialog(page, video_input_formats())
                    return

                progress_bar.value = 1.0
                progress_bar.update()

                successful_count = summary.get("success", 0)
                total_count = summary.get("success", 0) + summary.get(
                    "failed", 0
                )

                lbl_status.value = t(
                    "msg_success_summary",
                    msg=t("msg_success"),
                    successful=successful_count,
                    total=total_count,
                )
                lbl_status.color = get_color("success")
                lbl_status.update()

                summary["terminal_log"] = redirector.get_logs()
                show_summary_dialog(page, summary)

        except (InterruptedError, Exception) as err:
            self.abort_requested = True
            print(f"[FAIL] {err}")

        finally:
            redirector.stop()
            self._close_cancel_dialog(page)

            if self.abort_requested:
                cleaned_count = summary.get("cleaned_files_count", 0)
                lbl_status.value = t(
                    "msg_process_cancelled", count=cleaned_count
                )
                lbl_status.color = get_color("error")
                lbl_status.update()

            self._restore_idle_ui(page, progress_bar, btn_action)