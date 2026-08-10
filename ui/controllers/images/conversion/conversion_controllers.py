import time
from pathlib import Path
from typing import Optional
import flet as ft

from src.image.conversion.file_conversion import file_converter
from src.image.conversion.directory_conversion import directory_converter
from ui.i18n import t
from ui.theme import COLOR_SUCCESS, COLOR_ERROR, COLOR_SUBTEXT, COLOR_PRIMARY, COLOR_TEXT
from ui.utils.conversion_utils import resolve_color_key_to_hex
from ui.utils.dialog_utils import show_summary_dialog


class ConversionFileController:
    """Controller responsible for managing single-file image conversion business logic."""

    def __init__(self):
        """Initializes internal state variables for single-file conversion processing."""
        self.selected_input: Optional[Path] = None
        self.selected_output_dir: Optional[Path] = None
        self.picker_active: bool = False

    def open_file_picker(self, picker: ft.FilePicker):
        """
        Opens the single file selection dialog if no picker operation is currently active.

        Args:
            picker (ft.FilePicker): FilePicker instance registered in page overlay.
        """
        if not self.picker_active:
            self.picker_active = True
            picker.pick_files(allow_multiple=False)

    def open_dir_picker(self, picker: ft.FilePicker):
        """
        Opens the directory selection dialog if no picker operation is currently active.

        Args:
            picker (ft.FilePicker): FilePicker instance registered in page overlay.
        """
        if not self.picker_active:
            self.picker_active = True
            picker.get_directory_path()

    def handle_file_result(self, e: ft.FilePickerResultEvent, lbl_file_path: ft.Text):
        """
        Handles the event result triggered by the input file picker.

        Args:
            e (ft.FilePickerResultEvent): Event payload containing selected files.
            lbl_file_path (ft.Text): UI label displaying the input file name.
        """
        self.picker_active = False
        if e.files and len(e.files) > 0:
            self.selected_input = Path(e.files[0].path)
            lbl_file_path.value = self.selected_input.name
            lbl_file_path.color = COLOR_TEXT
            lbl_file_path.update()

    def handle_dir_result(self, e: ft.FilePickerResultEvent, lbl_out_path: ft.Text):
        """
        Handles the event result triggered by the output directory picker.

        Args:
            e (ft.FilePickerResultEvent): Event payload containing selected path.
            lbl_out_path (ft.Text): UI label displaying output directory name.
        """
        self.picker_active = False
        if e.path:
            self.selected_output_dir = Path(e.path)
            lbl_out_path.value = self.selected_output_dir.name or str(self.selected_output_dir)
            lbl_out_path.color = COLOR_TEXT
            lbl_out_path.update()

    def execute_conversion(
        self,
        page: ft.Page,
        target_format: str,
        selected_color_key: str,
        lbl_status: ft.Text
    ):
        """
        Executes single-file image conversion and presents execution summary.

        Args:
            page (ft.Page): Current Flet window page instance.
            target_format (str): Desired output file format string.
            selected_color_key (str): Translation key representing the alpha channel replacement color.
            lbl_status (ft.Text): UI text label for real-time status messages.
        """
        # Validate file and output directory selections
        if not self.selected_input or not self.selected_output_dir:
            lbl_status.value = t("msg_select_required")
            lbl_status.color = COLOR_ERROR
            lbl_status.update()
            return

        target_fmt = target_format.lower()
        clean_color = resolve_color_key_to_hex(selected_color_key)
        out_file = self.selected_output_dir / f"{self.selected_input.stem}_converted.{target_fmt}"

        # Update initial processing state
        lbl_status.value = "Processando..."
        lbl_status.color = COLOR_SUBTEXT
        lbl_status.update()

        start_time = time.time()
        success = file_converter(
            input_path=self.selected_input,
            output_path=out_file,
            target_format=target_fmt,
            transparency_replacement_color=clean_color
        )
        elapsed = time.time() - start_time

        # Update UI according to conversion result
        if success:
            lbl_status.value = t("msg_success")
            lbl_status.color = COLOR_SUCCESS
        else:
            lbl_status.value = t("msg_error")
            lbl_status.color = COLOR_ERROR
        lbl_status.update()

        # Build metrics dictionary and trigger summary modal
        summary = {
            "total_files": 1,
            "success": 1 if success else 0,
            "failed": 0 if success else 1,
            "elapsed_seconds": elapsed,
            "errors": [] if success else [{"file": self.selected_input.name, "error": t("msg_error")}]
        }
        show_summary_dialog(page, summary)


class ConversionDirController:
    """Controller responsible for batch directory image conversion with interruption support."""

    def __init__(self):
        """Initializes state variables for batch directory conversion processing."""
        self.selected_input_dir: Optional[Path] = None
        self.selected_output_dir: Optional[Path] = None
        self.picker_active: bool = False
        self.is_processing: bool = False
        self.abort_requested: bool = False
        self.cancel_dialog: Optional[ft.AlertDialog] = None

    def open_dir_picker(self, picker: ft.FilePicker):
        """
        Opens directory picker if no file picker operation is active.

        Args:
            picker (ft.FilePicker): FilePicker instance registered in page overlay.
        """
        if not self.picker_active:
            self.picker_active = True
            picker.get_directory_path()

    def handle_in_dir_result(self, e: ft.FilePickerResultEvent, lbl_in_path: ft.Text):
        """
        Handles selection result from input directory picker.

        Args:
            e (ft.FilePickerResultEvent): Event payload containing selected directory.
            lbl_in_path (ft.Text): UI label component displaying input path.
        """
        self.picker_active = False
        if e.path:
            self.selected_input_dir = Path(e.path)
            lbl_in_path.value = self.selected_input_dir.name or str(self.selected_input_dir)
            lbl_in_path.color = COLOR_TEXT
            lbl_in_path.update()

    def handle_out_dir_result(self, e: ft.FilePickerResultEvent, lbl_out_path: ft.Text):
        """
        Handles selection result from output directory picker.

        Args:
            e (ft.FilePickerResultEvent): Event payload containing selected directory.
            lbl_out_path (ft.Text): UI label component displaying output path.
        """
        self.picker_active = False
        if e.path:
            self.selected_output_dir = Path(e.path)
            lbl_out_path.value = self.selected_output_dir.name or str(self.selected_output_dir)
            lbl_out_path.color = COLOR_TEXT
            lbl_out_path.update()

    def handle_action_click(
        self,
        page: ft.Page,
        target_format: str,
        selected_color_key: str,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton
    ):
        """
        Routes action button click event to execute conversion or prompt cancellation.

        Args:
            page (ft.Page): Current Flet window page instance.
            target_format (str): Desired output format string.
            selected_color_key (str): Selected background color key for transparency.
            lbl_status (ft.Text): UI label component displaying execution status.
            progress_bar (ft.ProgressBar): Progress indicator control.
            btn_action (ft.ElevatedButton): Main trigger action button.
        """
        if self.is_processing:
            self._confirm_cancel_process(page, lbl_status, progress_bar, btn_action)
        else:
            self.execute_conversion(
                page=page,
                target_format=target_format,
                selected_color_key=selected_color_key,
                lbl_status=lbl_status,
                progress_bar=progress_bar,
                btn_action=btn_action
            )

    def _confirm_cancel_process(
        self,
        page: ft.Page,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton
    ):
        """
        Displays confirmation modal to interrupt process and purge destination files.

        Args:
            page (ft.Page): Current Flet window page instance.
            lbl_status (ft.Text): UI label component displaying execution status.
            progress_bar (ft.ProgressBar): Progress indicator control.
            btn_action (ft.ElevatedButton): Main trigger action button.
        """
        def close_dialog(_):
            if self.cancel_dialog:
                self.cancel_dialog.open = False
                page.update()
                self.cancel_dialog = None

        def stop_and_cleanup(_):
            close_dialog(_)
            if self.is_processing:
                self.abort_requested = True
                lbl_status.value = "Cancelando e limpando arquivos gerados..."
                lbl_status.color = COLOR_ERROR
                lbl_status.update()

        self.cancel_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar Cancelamento", weight=ft.FontWeight.W_600),
            content=ft.Text(
                "Deseja realmente interromper o processamento?\nOs arquivos salvos nesta sessão no destino serão apagados.",
                size=13
            ),
            actions=[
                ft.TextButton("Não, Continuar", on_click=close_dialog),
                ft.ElevatedButton(
                    "Sim, Interromper e Apagar",
                    bgcolor="red",
                    color=COLOR_TEXT,
                    on_click=stop_and_cleanup
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.dialog = self.cancel_dialog
        self.cancel_dialog.open = True
        page.update()

    def execute_conversion(
        self,
        page: ft.Page,
        target_format: str,
        selected_color_key: str,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton
    ):
        """
        Executes batch directory image conversion and updates progress feedback.

        Args:
            page (ft.Page): Current Flet window page instance.
            target_format (str): Desired output image format.
            selected_color_key (str): Selected transparency replacement color key.
            lbl_status (ft.Text): UI label component for progress text updates.
            progress_bar (ft.ProgressBar): UI progress bar control.
            btn_action (ft.ElevatedButton): Action button control to switch button states.
        """
        # Validate directory choices
        if not self.selected_input_dir or not self.selected_output_dir:
            lbl_status.value = t("msg_select_required")
            lbl_status.color = COLOR_ERROR
            lbl_status.update()
            return

        self.is_processing = True
        self.abort_requested = False

        # Switch button appearance to indicate active processing
        btn_action.text = "PARAR PROCESSAMENTO"
        btn_action.icon = ft.icons.STOP
        btn_action.bgcolor = "red"
        btn_action.update()

        progress_bar.visible = True
        progress_bar.value = 0
        progress_bar.update()

        target_fmt = target_format.lower()
        clean_color = resolve_color_key_to_hex(selected_color_key)

        def update_progress(info):
            # Check user cancellation request
            if self.abort_requested:
                raise InterruptedError("CANCELLED_BY_USER")

            if info.total > 0:
                progress_bar.value = info.current / info.total
                filename = info.file_path.name if info.file_path else ''
                lbl_status.value = f"Processando: [{info.current}/{info.total}] - {filename}"
                progress_bar.update()
                lbl_status.update()

        summary = {}
        try:
            # Execute batch converter logic
            summary = directory_converter(
                input_dir=self.selected_input_dir,
                output_dir=self.selected_output_dir,
                target_format=target_fmt,
                transparency_replacement_color=clean_color,
                progress_callback=update_progress
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

                success_cnt = summary.get("success", summary.get("successful", 0))
                total_cnt = summary.get("total_files", summary.get("total", 0))

                lbl_status.value = f"{t('msg_success')} | Sucesso: {success_cnt} / {total_cnt}"
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

            # Handle cancellation cleanup and feedback
            if self.abort_requested:
                cleaned_count = summary.get("cleaned_files_count", 0)
                progress_bar.visible = False
                progress_bar.update()
                lbl_status.value = f"Processamento cancelado. {cleaned_count} arquivo(s) gerado(s) foram apagados."
                lbl_status.color = COLOR_ERROR

            # Reset controller processing states and UI button appearance
            self.is_processing = False
            self.abort_requested = False
            btn_action.text = t("btn_process")
            btn_action.icon = ft.icons.PLAY_ARROW
            btn_action.bgcolor = COLOR_PRIMARY
            btn_action.update()
            lbl_status.update()