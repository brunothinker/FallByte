import threading
import time
from pathlib import Path
from typing import List, Optional
import flet as ft

from src.video.conversion.directory_conversion import directory_converter
from src.video.conversion.file_conversion import file_converter
from ui.components.dialog_utils import show_summary_dialog
from ui.i18n import t
from ui.theme import COLOR_ERROR, COLOR_PRIMARY, COLOR_SUCCESS, COLOR_TEXT

SUPPORTED_VIDEO_CONVERSION_FORMATS: List[str] = [
    "mp4",
    "mkv",
    "webm",
    "mov",
    "avi",
    "wmv",
]


class VideoConversionController:
    """Controller managing single-file and batch directory video conversion business logic."""

    def __init__(self) -> None:
        """Initializes state variables for video conversion execution and safety guards."""
        self.selected_input: Optional[Path] = None
        self.selected_output_dir: Optional[Path] = None
        self.is_processing: bool = False
        self.abort_requested: bool = False
        self.picker_active: bool = False
        self.cancel_dialog: Optional[ft.AlertDialog] = None

    def open_picker(
        self, picker: ft.FilePicker, allow_directory: bool = False
    ) -> None:
        """Opens file or directory picker preventing concurrent window spawns."""
        if not self.picker_active:
            self.picker_active = True
            if allow_directory:
                picker.get_directory_path()
            else:
                picker.pick_files(allow_multiple=False)

    def handle_input_result(
        self, e: ft.FilePickerResultEvent, lbl_path: ft.Text
    ) -> None:
        """Handles selection result from input video file or directory picker."""
        self.picker_active = False
        if e.files and len(e.files) > 0:
            self.selected_input = Path(e.files[0].path)
        elif e.path:
            self.selected_input = Path(e.path)

        if self.selected_input:
            lbl_path.value = (
                self.selected_input.name or str(self.selected_input)
            )
            lbl_path.color = COLOR_TEXT
            lbl_path.update()

    def handle_output_result(
        self, e: ft.FilePickerResultEvent, lbl_path: ft.Text
    ) -> None:
        """Handles selection result from output directory picker."""
        self.picker_active = False
        if e.path:
            self.selected_output_dir = Path(e.path)
            lbl_path.value = (
                self.selected_output_dir.name or str(self.selected_output_dir)
            )
            lbl_path.color = COLOR_TEXT
            lbl_path.update()

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
        if not self.selected_input or not self.selected_output_dir:
            lbl_status.value = t("msg_select_required")
            lbl_status.color = COLOR_ERROR
            lbl_status.update()
            return

        if self.selected_input.is_file():
            self._execute_single_file(page, target_format, lbl_status)
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
    ) -> None:
        """Executes single-file video conversion flow and presents summary dialog."""
        target_fmt = target_format.lower()
        out_file = (
            self.selected_output_dir
            / f"{self.selected_input.stem}_converted.{target_fmt}"
        )

        lbl_status.value = t("msg_processing")
        lbl_status.color = COLOR_TEXT
        lbl_status.update()

        start_time = time.time()
        orig_bytes = self.selected_input.stat().st_size
        success = file_converter(
            input_path=self.selected_input,
            output_path=out_file,
            target_format=target_fmt,
        )
        elapsed = time.time() - start_time
        comp_bytes = out_file.stat().st_size if success and out_file.exists() else 0

        if success:
            lbl_status.value = t("msg_success")
            lbl_status.color = COLOR_SUCCESS
        else:
            lbl_status.value = t("msg_error")
            lbl_status.color = COLOR_ERROR
        lbl_status.update()

        summary = {
            "total_files": 1,
            "success": 1 if success else 0,
            "failed": 0 if success else 1,
            "elapsed_seconds": round(elapsed, 2),
            "original_bytes": orig_bytes,
            "compressed_bytes": comp_bytes,
            "errors": []
            if success
            else [{"file": self.selected_input.name, "error": t("msg_error")}],
        }
        show_summary_dialog(page, summary)

    def _execute_batch_directory(
        self,
        page: ft.Page,
        target_format: str,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Executes batch directory video conversion with progress tracking and interruption."""
        self.is_processing = True
        self.abort_requested = False

        btn_action.text = t("btn_stop_process")
        btn_action.icon = ft.icons.STOP
        btn_action.bgcolor = COLOR_ERROR
        btn_action.update()

        progress_bar.visible = True
        progress_bar.value = 0
        progress_bar.update()

        target_fmt = target_format.lower()

        def update_progress(info):
            if self.abort_requested:
                raise InterruptedError("CANCELLED_BY_USER")

            if info.total_files > 0:
                progress_bar.value = info.current_file_index / info.total_files
                filename = info.file_path.name if info.file_path else ""
                lbl_status.value = t(
                    "msg_converting_progress",
                    current=info.current_file_index,
                    total=info.total_files,
                    filename=filename,
                )
                progress_bar.update()
                lbl_status.update()

        summary = {}
        try:
            summary = directory_converter(
                input_dir=self.selected_input,
                output_dir=self.selected_output_dir,
                target_format=target_fmt,
                progress_callback=update_progress,
            )

            if summary.get("cancelled", False):
                self.abort_requested = True

            if self.cancel_dialog and self.cancel_dialog.open:
                self.cancel_dialog.open = False
                page.update()
                self.cancel_dialog = None

            if not self.abort_requested:
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
                lbl_status.color = COLOR_SUCCESS
                lbl_status.update()

                show_summary_dialog(page, summary)

        except (InterruptedError, Exception):
            self.abort_requested = True

        finally:
            if self.cancel_dialog and self.cancel_dialog.open:
                self.cancel_dialog.open = False
                page.update()
                self.cancel_dialog = None

            if self.abort_requested:
                cleaned_count = summary.get("cleaned_files_count", 0)
                progress_bar.visible = False
                progress_bar.update()
                lbl_status.value = t(
                    "msg_process_cancelled", count=cleaned_count
                )
                lbl_status.color = COLOR_ERROR

            self.is_processing = False
            self.abort_requested = False
            btn_action.text = t("btn_process")
            btn_action.icon = ft.icons.PLAY_ARROW
            btn_action.bgcolor = COLOR_PRIMARY
            btn_action.update()
            lbl_status.update()

    def _confirm_cancel_process(
        self,
        page: ft.Page,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Displays modal confirming execution abort and session cleanup."""

        def close_dialog(_):
            if self.cancel_dialog:
                self.cancel_dialog.open = False
                page.update()
                self.cancel_dialog = None

        def stop_and_cleanup(_):
            close_dialog(_)
            if self.is_processing:
                self.abort_requested = True
                lbl_status.value = t("msg_cancelling")
                lbl_status.color = COLOR_ERROR
                lbl_status.update()

        self.cancel_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(
                t("dialog_cancel_title"), weight=ft.FontWeight.W_600
            ),
            content=ft.Text(t("dialog_cancel_body"), size=13),
            actions=[
                ft.TextButton(t("btn_keep_running"), on_click=close_dialog),
                ft.ElevatedButton(
                    t("btn_stop_and_delete"),
                    bgcolor=COLOR_ERROR,
                    color=COLOR_TEXT,
                    on_click=stop_and_cleanup,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.dialog = self.cancel_dialog
        self.cancel_dialog.open = True
        page.update()