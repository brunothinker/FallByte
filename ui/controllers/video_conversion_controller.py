import logging
import threading
import time

import flet as ft

from src.formats import (
    VIDEO_TARGET_FORMATS as SUPPORTED_VIDEO_CONVERSION_FORMATS,
)
from src.utils.output_naming import unique_conversion_output_path
from src.utils.progress import ProgressInfo
from src.video.video_directory_conversion import directory_converter
from src.video.video_file_conversion import file_converter
from ui.components.dialog_utils import (
    show_no_supported_files_dialog,
    show_summary_dialog,
)
from ui.controllers.base_controller import BaseController
from ui.i18n import t
from ui.theme import get_color
from ui.utils.format_utils import video_input_formats
from ui.utils.log_capture import TextRedirector

logger = logging.getLogger(__name__)

__all__ = [
    "SUPPORTED_VIDEO_CONVERSION_FORMATS",
    "VideoConversionController",
]


class VideoConversionController(BaseController):
    """Controller managing single-file and batch directory video conversion business logic."""

    def __init__(self) -> None:
        """Initializes state variables for video conversion execution and safety guards."""
        super().__init__()
        self.cancel_event: threading.Event = threading.Event()

    def _on_cancel_confirmed(self) -> None:
        """Hook override triggering cancellation event for active video conversion processes."""
        self.cancel_event.set()

    def handle_action_click(
        self,
        page: ft.Page,
        target_format: str,
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
            self.execute_conversion(
                page,
                target_format,
                lbl_status,
                progress_bar,
                btn_action,
            )

    def execute_conversion(
        self,
        page: ft.Page,
        target_format: str,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Routes execution to single video file or batch directory converter."""
        validation_error = self.validate_paths()
        if validation_error or not self.selected_input:
            lbl_status.value = t(validation_error or "msg_select_required")
            lbl_status.color = get_color("error")
            lbl_status.update()
            return

        if self.selected_input.is_file():
            threading.Thread(
                target=self._execute_single_file,
                args=(
                    page,
                    target_format,
                    lbl_status,
                    progress_bar,
                    btn_action,
                ),
                daemon=True,
            ).start()
        else:
            threading.Thread(
                target=self._execute_batch_directory,
                args=(
                    page,
                    target_format,
                    lbl_status,
                    progress_bar,
                    btn_action,
                ),
                daemon=True,
            ).start()

    def _execute_single_file(
        self,
        page: ft.Page,
        target_format: str,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Executes single-file video conversion flow and presents summary dialog."""
        if not self.selected_input or not self.selected_output_dir:
            return

        filename = self.selected_input.name
        self._set_processing_ui(page, progress_bar, btn_action)
        self.cancel_event.clear()

        target_fmt = target_format.lower()
        out_file = unique_conversion_output_path(
            input_path=self.selected_input,
            output_dir=self.selected_output_dir,
            target_format=target_fmt,
        )

        lbl_status.value = t(
            "msg_converting_progress",
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
                    "msg_converting_progress",
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
            success = file_converter(
                input_path=self.selected_input,
                output_path=out_file,
                target_format=target_fmt,
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
        comp_bytes = out_file.stat().st_size if success and out_file.exists() else 0

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
                else [{"file": filename, "error": t("msg_error")}],
            }
            show_summary_dialog(page, summary)
        else:
            if out_file.exists():
                try:
                    out_file.unlink()
                except OSError:
                    pass
            lbl_status.value = t("msg_process_cancelled", count=1)
            lbl_status.color = get_color("error")
            lbl_status.update()

        self._restore_idle_ui(page, progress_bar, btn_action)

    def _execute_batch_directory(
        self,
        page: ft.Page,
        target_format: str,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Executes batch directory video conversion with progress tracking and interruption."""
        if not self.selected_input or not self.selected_output_dir:
            return

        self._set_processing_ui(page, progress_bar, btn_action)
        self.cancel_event.clear()
        progress_bar.value = 0
        progress_bar.update()

        target_fmt = target_format.lower()

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
                    "msg_converting_progress",
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
            summary = directory_converter(
                input_dir=self.selected_input,
                output_dir=self.selected_output_dir,
                target_format=target_fmt,
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

                success_cnt = summary.get("success", 0)
                total_cnt = summary.get("success", 0) + summary.get("failed", 0)

                lbl_status.value = t(
                    "msg_success_summary",
                    msg=t("msg_success"),
                    successful=success_cnt,
                    total=total_cnt,
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