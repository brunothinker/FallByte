from pathlib import Path
from typing import Optional
import flet as ft

from src.image.conversion.file_converter import file_converter
from src.image.conversion.directory_converter import directory_converter
from ui.i18n import t
from ui.theme import COLOR_SUCCESS, COLOR_ERROR, COLOR_SUBTEXT, COLOR_TEXT
from ui.utils.conversion_utils import normalize_hex_color


class ConversionFileController:
    """Controller responsible for the single-file image conversion business logic."""

    def __init__(self):
        self.selected_input: Optional[Path] = None
        self.selected_output_dir: Optional[Path] = None
        self.picker_active: bool = False

    def open_file_picker(self, picker: ft.FilePicker):
        if not self.picker_active:
            self.picker_active = True
            picker.pick_files(allow_multiple=False)

    def open_dir_picker(self, picker: ft.FilePicker):
        if not self.picker_active:
            self.picker_active = True
            picker.get_directory_path()

    def handle_file_result(self, e: ft.FilePickerResultEvent, lbl_file_path: ft.Text):
        self.picker_active = False
        if e.files and len(e.files) > 0:
            self.selected_input = Path(e.files[0].path)
            lbl_file_path.value = self.selected_input.name
            lbl_file_path.color = COLOR_TEXT
            lbl_file_path.update()

    def handle_dir_result(self, e: ft.FilePickerResultEvent, lbl_out_path: ft.Text):
        self.picker_active = False
        if e.path:
            self.selected_output_dir = Path(e.path)
            lbl_out_path.value = self.selected_output_dir.name or str(self.selected_output_dir)
            lbl_out_path.color = COLOR_TEXT
            lbl_out_path.update()

    def execute_conversion(
        self,
        target_format: str,
        raw_color: str,
        lbl_status: ft.Text
    ):
        if not self.selected_input or not self.selected_output_dir:
            lbl_status.value = t("msg_select_required")
            lbl_status.color = COLOR_ERROR
            lbl_status.update()
            return

        target_fmt = target_format.lower()
        clean_color = normalize_hex_color(raw_color)
        out_file = self.selected_output_dir / f"{self.selected_input.stem}_converted.{target_fmt}"

        lbl_status.value = "Processando..."
        lbl_status.color = COLOR_SUBTEXT
        lbl_status.update()

        success = file_converter(
            input_path=self.selected_input,
            output_path=out_file,
            target_format=target_fmt,
            transparency_replacement_color=clean_color
        )

        if success:
            lbl_status.value = t("msg_success")
            lbl_status.color = COLOR_SUCCESS
        else:
            lbl_status.value = t("msg_error")
            lbl_status.color = COLOR_ERROR
        lbl_status.update()


class ConversionDirController:
    """Controller responsible for batch directory image conversion business logic."""

    def __init__(self):
        self.selected_input_dir: Optional[Path] = None
        self.selected_output_dir: Optional[Path] = None
        self.picker_active: bool = False

    def open_dir_picker(self, picker: ft.FilePicker):
        if not self.picker_active:
            self.picker_active = True
            picker.get_directory_path()

    def handle_in_dir_result(self, e: ft.FilePickerResultEvent, lbl_in_path: ft.Text):
        self.picker_active = False
        if e.path:
            self.selected_input_dir = Path(e.path)
            lbl_in_path.value = self.selected_input_dir.name or str(self.selected_input_dir)
            lbl_in_path.color = COLOR_TEXT
            lbl_in_path.update()

    def handle_out_dir_result(self, e: ft.FilePickerResultEvent, lbl_out_path: ft.Text):
        self.picker_active = False
        if e.path:
            self.selected_output_dir = Path(e.path)
            lbl_out_path.value = self.selected_output_dir.name or str(self.selected_output_dir)
            lbl_out_path.color = COLOR_TEXT
            lbl_out_path.update()

    def execute_conversion(
        self,
        target_format: str,
        raw_color: str,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar
    ):
        if not self.selected_input_dir or not self.selected_output_dir:
            lbl_status.value = t("msg_select_required")
            lbl_status.color = COLOR_ERROR
            lbl_status.update()
            return

        progress_bar.visible = True
        progress_bar.value = 0
        progress_bar.update()

        target_fmt = target_format.lower()
        clean_color = normalize_hex_color(raw_color)

        def update_progress(info):
            if info.total > 0:
                progress_bar.value = info.current / info.total
                filename = info.file_path.name if info.file_path else ''
                lbl_status.value = f"Processando: [{info.current}/{info.total}] - {filename}"
                progress_bar.update()
                lbl_status.update()

        summary = directory_converter(
            input_dir=self.selected_input_dir,
            output_dir=self.selected_output_dir,
            target_format=target_fmt,
            transparency_replacement_color=clean_color,
            progress_callback=update_progress
        )

        progress_bar.value = 1.0
        progress_bar.update()

        lbl_status.value = f"{t('msg_success')} | Sucesso: {summary['successful']} / {summary['total_files']}"
        lbl_status.color = COLOR_SUCCESS
        lbl_status.update()