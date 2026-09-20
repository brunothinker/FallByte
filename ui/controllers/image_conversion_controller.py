import logging
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional
import flet as ft

from src.image.conversion.directory_conversion import directory_converter
from src.image.conversion.file_conversion import file_converter
from ui.components.dialog_utils import show_summary_dialog
from ui.i18n import t
from ui.theme import COLOR_ERROR, COLOR_PRIMARY, COLOR_SUCCESS, COLOR_TEXT
from ui.utils.conversion_utils import resolve_color_key_to_hex


class TextRedirector(logging.Handler):
    """Redirects sys.stdout, sys.stderr and Python logging streams to accumulate console logs in a buffer."""

    def __init__(self) -> None:
        """Initializes buffer and reference variables for standard streams and logger."""
        super().__init__()
        self._buffer: List[str] = []
        self._stdout = sys.stdout
        self._stderr = sys.stderr

    def write(self, message: str) -> None:
        """Writes a message to the buffer and forwards it to the original stdout stream.

        Args:
            message: The string message to write to the console stream.
        """
        if message:
            self._buffer.append(message)
            self._stdout.write(message)

    def flush(self) -> None:
        """Flushes the original stdout stream buffer."""
        self._stdout.flush()

    def emit(self, record: logging.LogRecord) -> None:
        """Captures Python logging module records into the internal buffer.

        Args:
            record: The LogRecord instance emitted by the logging system.
        """
        try:
            msg = self.format(record)
            self._buffer.append(f"[{record.levelname}] {msg}\n")
        except Exception:
            self.handleError(record)

    def start(self) -> None:
        """Hijacks sys.stdout, sys.stderr streams and attaches handler to root logger."""
        sys.stdout = self
        sys.stderr = self
        logging.getLogger().addHandler(self)

    def stop(self) -> None:
        """Restores original sys.stdout, sys.stderr streams and detaches logging handler."""
        sys.stdout = self._stdout
        sys.stderr = self._stderr
        logging.getLogger().removeHandler(self)

    def get_logs(self) -> str:
        """Returns accumulated console output as a single string.

        Returns:
            A single joined string containing all buffered console logs.
        """
        return "".join(self._buffer)


class ConversionController:
    """Controller managing single-file and batch directory image conversion business logic."""

    def __init__(self) -> None:
        """Initializes state variables for conversion execution and safety guards."""
        self.selected_input: Optional[Path] = None
        self.selected_output_dir: Optional[Path] = None
        self.is_processing: bool = False
        self.abort_requested: bool = False
        self.picker_active: bool = False
        self.cancel_dialog: Optional[ft.AlertDialog] = None

    def open_picker(
        self, picker: ft.FilePicker, allow_directory: bool = False
    ) -> None:
        """Opens file or directory picker preventing concurrent window spawns.

        Args:
            picker: The Flet FilePicker component instance.
            allow_directory: Flag indicating whether to pick directories instead of files.
        """
        if not self.picker_active:
            self.picker_active = True
            if allow_directory:
                picker.get_directory_path()
            else:
                picker.pick_files(allow_multiple=False)

    def handle_input_result(
        self,
        e: ft.FilePickerResultEvent,
        lbl_path: ft.Text,
        lbl_status: Optional[ft.Text] = None,
    ) -> None:
        """Handles selection result from input file or directory picker.

        Args:
            e: The FilePicker result event containing user selection paths.
            lbl_path: The Flet Text UI control to display the selected path name.
            lbl_status: Optional Flet Text UI control to clear previous status messages.
        """
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

            if lbl_status:
                lbl_status.value = ""
                lbl_status.update()

    def handle_output_result(
        self,
        e: ft.FilePickerResultEvent,
        lbl_path: ft.Text,
        lbl_status: Optional[ft.Text] = None,
    ) -> None:
        """Handles selection result from output directory picker.

        Args:
            e: The FilePicker result event containing user selection path.
            lbl_path: The Flet Text UI control to display the selected directory name.
            lbl_status: Optional Flet Text UI control to clear previous status messages.
        """
        self.picker_active = False
        if e.path:
            self.selected_output_dir = Path(e.path)
            lbl_path.value = (
                self.selected_output_dir.name or str(self.selected_output_dir)
            )
            lbl_path.color = COLOR_TEXT
            lbl_path.update()

            if lbl_status:
                lbl_status.value = ""
                lbl_status.update()

    def handle_action_click(
        self,
        page: ft.Page,
        target_format: str,
        selected_color_key: str,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Routes trigger button click to execute process or request cancellation.

        Args:
            page: Active Flet Page instance.
            target_format: Target image extension string (e.g. 'png', 'jpg').
            selected_color_key: Key identifying transparency replacement color.
            lbl_status: Text control rendering process feedback text.
            progress_bar: ProgressBar control rendering active execution progress.
            btn_action: Primary process trigger button control.
        """
        if self.is_processing:
            self._confirm_cancel_process(
                page, lbl_status, progress_bar, btn_action
            )
        else:
            self.execute_conversion(
                page,
                target_format,
                selected_color_key,
                lbl_status,
                progress_bar,
                btn_action,
            )

    def execute_conversion(
        self,
        page: ft.Page,
        target_format: str,
        selected_color_key: str,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Routes execution to single file or batch directory converter.

        Args:
            page: Active Flet Page instance.
            target_format: Target image extension string.
            selected_color_key: Key identifying transparency replacement color.
            lbl_status: Text control rendering process feedback text.
            progress_bar: ProgressBar control rendering active execution progress.
            btn_action: Primary process trigger button control.
        """
        if not self.selected_input or not self.selected_output_dir:
            lbl_status.value = t("msg_select_required")
            lbl_status.color = COLOR_ERROR
            lbl_status.update()
            return

        if self.selected_input.is_file():
            threading.Thread(
                target=self._execute_single_file,
                args=(
                    page,
                    target_format,
                    selected_color_key,
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
                    selected_color_key,
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
        selected_color_key: str,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Executes single-file image conversion flow and presents summary dialog.

        Args:
            page: Active Flet Page instance.
            target_format: Target image extension string.
            selected_color_key: Key identifying transparency replacement color.
            lbl_status: Text control rendering process feedback text.
            progress_bar: ProgressBar control rendering active execution progress.
            btn_action: Primary process trigger button control.
        """
        self.is_processing = True
        self.abort_requested = False

        btn_action.text = t("btn_stop_process")
        btn_action.icon = ft.icons.STOP
        btn_action.bgcolor = COLOR_ERROR
        btn_action.update()

        progress_bar.visible = True
        progress_bar.value = None
        progress_bar.update()

        target_fmt = target_format.lower()
        clean_color = resolve_color_key_to_hex(selected_color_key)
        out_file = (
            self.selected_output_dir
            / f"{self.selected_input.stem}_converted.{target_fmt}"
        )

        lbl_status.value = t(
            "msg_converting_progress",
            current=1,
            total=1,
            filename=self.selected_input.name,
        )
        lbl_status.color = COLOR_TEXT
        lbl_status.update()

        redirector = TextRedirector()
        redirector.start()

        start_time = time.time()
        success = False

        try:
            success = file_converter(
                input_path=self.selected_input,
                output_path=out_file,
                target_format=target_fmt,
                transparency_replacement_color=clean_color,
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

        if self.cancel_dialog and self.cancel_dialog.open:
            self.cancel_dialog.open = False
            page.update()
            self.cancel_dialog = None

        progress_bar.visible = False
        progress_bar.update()

        if not self.abort_requested:
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
                "elapsed_seconds": elapsed,
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
            lbl_status.color = COLOR_ERROR

        self.is_processing = False
        self.abort_requested = False
        btn_action.text = t("btn_process")
        btn_action.icon = ft.icons.PLAY_ARROW
        btn_action.bgcolor = COLOR_PRIMARY
        btn_action.update()
        lbl_status.update()

    def _execute_batch_directory(
        self,
        page: ft.Page,
        target_format: str,
        selected_color_key: str,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Executes batch directory image conversion with progress tracking and interruption.

        Args:
            page: Active Flet Page instance.
            target_format: Target image extension string.
            selected_color_key: Key identifying transparency replacement color.
            lbl_status: Text control rendering process feedback text.
            progress_bar: ProgressBar control rendering active execution progress.
            btn_action: Primary process trigger button control.
        """
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
        clean_color = resolve_color_key_to_hex(selected_color_key)

        redirector = TextRedirector()
        redirector.start()

        def update_progress(info) -> None:
            """Callback function handling batch item progress and user cancellation checks.

            Args:
                info: Data object carrying file count and current item metadata.

            Raises:
                InterruptedError: If user requested process cancellation.
            """
            if self.abort_requested:
                raise InterruptedError("CANCELLED_BY_USER")

            if info.total > 0:
                progress_bar.value = info.current / info.total
                filename = info.file_path.name if info.file_path else ""

                print(f"[OK] {filename}")

                lbl_status.value = t(
                    "msg_converting_progress",
                    current=info.current,
                    total=info.total,
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
                transparency_replacement_color=clean_color,
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

                success_cnt = summary.get(
                    "success", summary.get("successful", 0)
                )
                total_cnt = summary.get("total_files", summary.get("total", 0))

                lbl_status.value = t(
                    "msg_success_summary",
                    msg=t("msg_success"),
                    successful=success_cnt,
                    total=total_cnt,
                )
                lbl_status.color = COLOR_SUCCESS
                lbl_status.update()

                summary["terminal_log"] = redirector.get_logs()
                show_summary_dialog(page, summary)

        except (InterruptedError, Exception) as err:
            self.abort_requested = True
            print(f"[FAIL] {err}")

        finally:
            redirector.stop()

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
        """Displays modal confirming execution abort and session cleanup.

        Args:
            page: Active Flet Page instance.
            lbl_status: Text control rendering process feedback text.
            progress_bar: ProgressBar control rendering active execution progress.
            btn_action: Primary process trigger button control.
        """

        def close_dialog(_: ft.ControlEvent) -> None:
            """Closes active cancellation confirmation dialog."""
            if self.cancel_dialog:
                self.cancel_dialog.open = False
                page.update()
                self.cancel_dialog = None

        def stop_and_cleanup(_: ft.ControlEvent) -> None:
            """Triggers cancellation flag and updates status feedback."""
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