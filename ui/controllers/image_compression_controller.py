import threading
import time

import flet as ft

from src.image.image_directory_compression import directory_compressor
from src.image.image_file_compression import file_compressor
from ui.components.dialog_utils import (
    show_no_supported_files_dialog,
    show_summary_dialog,
)
from ui.controllers.base_controller import BaseController
from ui.i18n import t
from ui.theme import get_color
from ui.utils.format_utils import image_compression_formats
from ui.utils.log_capture import TextRedirector


class CompressionController(BaseController):
    """Controller managing single-file and batch directory image compression business logic."""

    def __init__(self) -> None:
        """Initializes state variables for image compression execution and safety guards."""
        super().__init__()

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
        """Executes single-file or batch directory image compression."""
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
            threading.Thread(
                target=self._run_batch_compression,
                args=(page, quality, lbl_status, progress_bar, btn_action),
                daemon=True,
            ).start()

    def _execute_single_file(
        self,
        page: ft.Page,
        quality: int,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Executes single-file image compression flow and presents summary dialog."""
        if not self.selected_input or not self.selected_output_dir:
            return

        self._set_processing_ui(page, progress_bar, btn_action)

        out_file = self.selected_output_dir / self.selected_input.name
        lbl_status.value = t(
            "msg_compressing_progress",
            current=1,
            total=1,
            filename=self.selected_input.name,
        )
        lbl_status.color = get_color("text")
        lbl_status.update()

        redirector = TextRedirector()
        redirector.start()

        start_time = time.time()
        orig_bytes = self.selected_input.stat().st_size
        success = False

        try:
            success = file_compressor(
                input_path=self.selected_input,
                output_path=out_file,
                quality=quality,
            )
            if success:
                print(f"[OK] {self.selected_input.name}")
            else:
                print(f"[FAIL] {self.selected_input.name}")
        except Exception as err:
            success = False
            print(f"[ERROR] {self.selected_input.name}: {err}")
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
                else [{"file": self.selected_input.name, "error": t("msg_error")}],
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

    def _run_batch_compression(
        self,
        page: ft.Page,
        quality: int,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Executes batch directory image compression and updates progress indicators."""
        if not self.selected_input or not self.selected_output_dir:
            return

        self._set_processing_ui(page, progress_bar, btn_action)
        progress_bar.value = 0
        progress_bar.update()

        def update_progress(info) -> None:
            if self.abort_requested:
                raise InterruptedError("CANCELLED_BY_USER")

            if info.total > 0:
                progress_bar.value = info.current / info.total
                filename = info.file_path.name if info.file_path else ""

                if info.success:
                    print(f"[OK] {filename}")
                else:
                    print(f"[FAIL] {filename}")

                lbl_status.value = t(
                    "msg_compressing_progress",
                    current=info.current,
                    total=info.total,
                    filename=filename,
                )
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
            )

            if summary.get("cancelled", False):
                self.abort_requested = True

            self._close_cancel_dialog(page)

            if not self.abort_requested:
                if summary.get("no_files", False):
                    lbl_status.value = ""
                    lbl_status.update()
                    self._restore_idle_ui(page, progress_bar, btn_action)
                    show_no_supported_files_dialog(page, image_compression_formats())
                    return

                progress_bar.value = 1.0
                progress_bar.update()

                success_cnt = summary.get("success", summary.get("successful", 0))
                total_cnt = summary.get("total_files", summary.get("total", 0))

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