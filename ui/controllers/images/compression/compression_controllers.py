import time
from pathlib import Path
from typing import Optional, List, Set
import flet as ft

from src.image.compression.file_compression import file_compressor
from src.image.compression.directory_compression import directory_compressor
from ui.i18n import t
from ui.theme import (
    COLOR_PRIMARY,
    COLOR_TEXT,
    COLOR_SUBTEXT,
    COLOR_SUCCESS,
    COLOR_ERROR,
)
from ui.utils.compression_utils import validate_quality_value
from ui.utils.dialog_utils import show_summary_dialog

SUPPORTED_COMPRESSION_EXTS: Set[str] = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif", ".bmp"}


class CompressionFileController:
    """Controller responsible for single-file image compression business logic."""

    def __init__(self) -> None:
        """Initializes internal state variables for single-file compression operations."""
        self.selected_input: Optional[Path] = None
        self.selected_output_dir: Optional[Path] = None
        self.picker_active: bool = False

    def open_file_picker(self, picker: ft.FilePicker) -> None:
        """
        Opens the single file selection picker if no picker operation is active.

        Args:
            picker (ft.FilePicker): FilePicker control instance registered in page overlay.
        """
        if not self.picker_active:
            self.picker_active = True
            picker.pick_files(allow_multiple=False)

    def open_dir_picker(self, picker: ft.FilePicker) -> None:
        """
        Opens the output directory picker if no picker operation is active.

        Args:
            picker (ft.FilePicker): FilePicker control instance registered in page overlay.
        """
        if not self.picker_active:
            self.picker_active = True
            picker.get_directory_path()

    def handle_file_result(self, e: ft.FilePickerResultEvent, lbl_file_path: ft.Text) -> None:
        """
        Handles event result from input file picker.

        Args:
            e (ft.FilePickerResultEvent): Event payload containing selected files.
            lbl_file_path (ft.Text): UI label component displaying selected input path.
        """
        self.picker_active = False
        if e.files and len(e.files) > 0:
            self.selected_input = Path(e.files[0].path)
            lbl_file_path.value = self.selected_input.name
            lbl_file_path.color = COLOR_TEXT
            lbl_file_path.update()

    def handle_dir_result(self, e: ft.FilePickerResultEvent, lbl_out_path: ft.Text) -> None:
        """
        Handles event result from output directory picker.

        Args:
            e (ft.FilePickerResultEvent): Event payload containing selected directory path.
            lbl_out_path (ft.Text): UI label component displaying selected output path.
        """
        self.picker_active = False
        if e.path:
            self.selected_output_dir = Path(e.path)
            lbl_out_path.value = self.selected_output_dir.name or str(self.selected_output_dir)
            lbl_out_path.color = COLOR_TEXT
            lbl_out_path.update()

    def sync_from_slider(self, e: ft.ControlEvent, txt_quality: ft.TextField) -> None:
        """
        Synchronizes text field value when slider value changes.

        Args:
            e (ft.ControlEvent): Event payload triggered by slider state change.
            txt_quality (ft.TextField): Quality percentage text field component.
        """
        if e.control.value is not None:
            q = validate_quality_value(e.control.value)
            txt_quality.value = str(q)
            txt_quality.update()

    def sync_from_text(self, e: ft.ControlEvent, slider_quality: ft.Slider) -> None:
        """
        Synchronizes slider value when text field value changes.

        Args:
            e (ft.ControlEvent): Event payload triggered by text input change.
            slider_quality (ft.Slider): Quality percentage slider component.
        """
        raw_val = e.control.value.strip() if e.control.value else ""
        if not raw_val:
            return
        try:
            val = int(raw_val)
            if 1 <= val <= 100:
                slider_quality.value = val
                slider_quality.update()
        except ValueError:
            pass

    def validate_text_blur(self, e: ft.ControlEvent, slider_quality: ft.Slider, txt_quality: ft.TextField) -> None:
        """
        Validates quality value on text field focus loss (blur event).

        Args:
            e (ft.ControlEvent): Blur event payload.
            slider_quality (ft.Slider): Quality percentage slider component.
            txt_quality (ft.TextField): Quality percentage text field component.
        """
        q = validate_quality_value(e.control.value, default=int(slider_quality.value))
        txt_quality.value = str(q)
        slider_quality.value = q
        txt_quality.update()
        slider_quality.update()

    def execute_compression(self, page: ft.Page, quality: int, lbl_status: ft.Text) -> None:
        """
        Executes single-file compression and presents execution summary modal upon completion.

        Args:
            page (ft.Page): Current Flet page instance.
            quality (int): Target compression quality percentage.
            lbl_status (ft.Text): UI label displaying current execution status.
        """
        if not self.selected_input or not self.selected_output_dir:
            lbl_status.value = t("msg_select_required")
            lbl_status.color = COLOR_ERROR
            lbl_status.update()
            return

        out_file = self.selected_output_dir / self.selected_input.name

        lbl_status.value = "Processando..."
        lbl_status.color = COLOR_SUBTEXT
        lbl_status.update()

        start_time = time.time()
        success = file_compressor(
            input_path=self.selected_input,
            output_path=out_file,
            quality=quality
        )
        elapsed = time.time() - start_time

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
            "errors": [] if success else [{"file": self.selected_input.name, "error": t("msg_error")}]
        }
        show_summary_dialog(page, summary)


class CompressionDirController:
    """Controller responsible for batch directory compression with pre-flight checks and cancellation."""

    def __init__(self) -> None:
        """Initializes state variables for batch directory compression processing."""
        self.selected_input_dir: Optional[Path] = None
        self.selected_output_dir: Optional[Path] = None
        self.is_processing: bool = False
        self.abort_requested: bool = False
        self.cancel_dialog: Optional[ft.AlertDialog] = None
        self.picker_active: bool = False

    def open_dir_picker(self, picker: ft.FilePicker) -> None:
        """
        Opens directory picker if no file picker operation is active.

        Args:
            picker (ft.FilePicker): FilePicker instance registered in page overlay.
        """
        if not self.picker_active:
            self.picker_active = True
            picker.get_directory_path()

    def handle_in_dir_result(self, e: ft.FilePickerResultEvent, lbl_in_path: ft.Text) -> None:
        """
        Handles selection result from input directory picker.

        Args:
            e (ft.FilePickerResultEvent): Event payload containing selected path.
            lbl_in_path (ft.Text): UI label component displaying input path.
        """
        self.picker_active = False
        if e.path:
            self.selected_input_dir = Path(e.path)
            lbl_in_path.value = self.selected_input_dir.name or str(self.selected_input_dir)
            lbl_in_path.color = COLOR_TEXT
            lbl_in_path.update()

    def handle_out_dir_result(self, e: ft.FilePickerResultEvent, lbl_out_path: ft.Text) -> None:
        """
        Handles selection result from output directory picker.

        Args:
            e (ft.FilePickerResultEvent): Event payload containing selected path.
            lbl_out_path (ft.Text): UI label component displaying output path.
        """
        self.picker_active = False
        if e.path:
            self.selected_output_dir = Path(e.path)
            lbl_out_path.value = self.selected_output_dir.name or str(self.selected_output_dir)
            lbl_out_path.color = COLOR_TEXT
            lbl_out_path.update()

    def sync_from_slider(self, e: ft.ControlEvent, txt_quality: ft.TextField) -> None:
        """
        Synchronizes quality text field with slider movement.

        Args:
            e (ft.ControlEvent): Slider event payload.
            txt_quality (ft.TextField): Quality percentage text input control.
        """
        if e.control.value is not None:
            q = validate_quality_value(e.control.value)
            txt_quality.value = str(q)
            txt_quality.update()

    def sync_from_text(self, e: ft.ControlEvent, slider_quality: ft.Slider) -> None:
        """
        Synchronizes quality slider with direct text input.

        Args:
            e (ft.ControlEvent): Text field event payload.
            slider_quality (ft.Slider): Quality percentage slider control.
        """
        raw_val = e.control.value.strip() if e.control.value else ""
        if not raw_val:
            return
        try:
            val = int(raw_val)
            if 1 <= val <= 100:
                slider_quality.value = val
                slider_quality.update()
        except ValueError:
            pass

    def validate_text_blur(self, e: ft.ControlEvent, slider_quality: ft.Slider, txt_quality: ft.TextField) -> None:
        """
        Validates text input field when control loses focus.

        Args:
            e (ft.ControlEvent): Text field blur event payload.
            slider_quality (ft.Slider): Quality percentage slider control.
            txt_quality (ft.TextField): Quality percentage text input control.
        """
        q = validate_quality_value(e.control.value, default=int(slider_quality.value))
        txt_quality.value = str(q)
        slider_quality.value = q
        txt_quality.update()
        slider_quality.update()

    def handle_action_click(
        self,
        page: ft.Page,
        quality: int,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton
    ) -> None:
        """
        Routes action button click event to start batch execution or prompt cancellation.

        Args:
            page (ft.Page): Current Flet window page instance.
            quality (int): Selected quality percentage setting.
            lbl_status (ft.Text): UI label component displaying execution status.
            progress_bar (ft.ProgressBar): Progress indicator control.
            btn_action (ft.ElevatedButton): Main trigger action button.
        """
        if self.is_processing:
            self._confirm_cancel_process(page, lbl_status, progress_bar, btn_action)
        else:
            self.prepare_and_execute(page, quality, lbl_status, progress_bar, btn_action)

    def prepare_and_execute(
        self,
        page: ft.Page,
        quality: int,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton
    ) -> None:
        """
        Performs pre-flight analysis for unsupported file extensions before starting compression.

        Args:
            page (ft.Page): Current Flet window page instance.
            quality (int): Selected quality percentage setting.
            lbl_status (ft.Text): UI status message label.
            progress_bar (ft.ProgressBar): Progress indicator control.
            btn_action (ft.ElevatedButton): Main trigger action button.
        """
        if not self.selected_input_dir or not self.selected_output_dir:
            lbl_status.value = t("msg_select_required")
            lbl_status.color = COLOR_ERROR
            lbl_status.update()
            return

        all_files = [f for f in self.selected_input_dir.rglob("*") if f.is_file()]
        supported_files: List[Path] = []
        unsupported_files: List[Path] = []

        for f in all_files:
            if f.suffix.lower() in SUPPORTED_COMPRESSION_EXTS:
                supported_files.append(f)
            else:
                unsupported_files.append(f)

        if len(unsupported_files) > 0:
            ext_set = {f.suffix.upper() for f in unsupported_files if f.suffix}
            sample_exts = ", ".join(list(ext_set)[:4]) if ext_set else "Sem extensão"

            def close_dialog(_):
                dialog.open = False
                page.update()

            def confirm_and_run(_):
                dialog.open = False
                page.update()
                self._run_compression(page, quality, lbl_status, progress_bar, btn_action)

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text(t("dialog_incompatible_title"), weight=ft.FontWeight.W_600),
                content=ft.Text(
                    t(
                        "dialog_incompatible_body",
                        unsupported_count=len(unsupported_files),
                        supported_count=len(supported_files),
                        sample_exts=sample_exts
                    ),
                    size=13
                ),
                actions=[
                    ft.TextButton(t("btn_cancel"), on_click=close_dialog),
                    ft.ElevatedButton(
                        t("btn_continue"),
                        bgcolor=COLOR_PRIMARY,
                        color=COLOR_TEXT,
                        on_click=confirm_and_run
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            page.dialog = dialog
            dialog.open = True
            page.update()
        else:
            self._run_compression(page, quality, lbl_status, progress_bar, btn_action)

    def _confirm_cancel_process(
        self,
        page: ft.Page,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton
    ) -> None:
        """
        Displays confirmation modal to interrupt process and purge destination files.

        Args:
            page (ft.Page): Current Flet window page instance.
            lbl_status (ft.Text): UI status message label.
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
                    bgcolor=COLOR_ERROR,
                    color=COLOR_TEXT,
                    on_click=stop_and_cleanup
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.dialog = self.cancel_dialog
        self.cancel_dialog.open = True
        page.update()

    def _run_compression(
        self,
        page: ft.Page,
        quality: int,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton
    ) -> None:
        """
        Executes batch directory compression and updates progress indicators.

        Args:
            page (ft.Page): Current Flet window page instance.
            quality (int): Target compression quality percentage.
            lbl_status (ft.Text): UI status label control.
            progress_bar (ft.ProgressBar): Progress indicator control.
            btn_action (ft.ElevatedButton): Action button control.
        """
        self.is_processing = True
        self.abort_requested = False

        btn_action.text = "PARAR PROCESSAMENTO"
        btn_action.icon = ft.icons.STOP
        btn_action.bgcolor = COLOR_ERROR
        btn_action.update()

        progress_bar.visible = True
        progress_bar.value = 0
        progress_bar.update()

        def update_progress(info):
            if self.abort_requested:
                raise InterruptedError("CANCELLED_BY_USER")

            if info.total > 0:
                progress_bar.value = info.current / info.total
                filename = info.file_path.name if info.file_path else ''
                lbl_status.value = f"Comprimindo: [{info.current}/{info.total}] - {filename}"
                progress_bar.update()
                lbl_status.update()

        summary = {}
        try:
            summary = directory_compressor(
                input_dir=self.selected_input_dir,
                output_dir=self.selected_output_dir,
                quality=quality,
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

                successful_count = summary.get('success', 0)
                total_count = summary.get('total_files', 0)

                lbl_status.value = f"{t('msg_success')} | Sucesso: {successful_count} / {total_count}"
                lbl_status.color = COLOR_SUCCESS

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
                lbl_status.value = f"Processamento cancelado. {cleaned_count} arquivo(s) gerado(s) foram apagados."
                lbl_status.color = COLOR_ERROR

            self.is_processing = False
            self.abort_requested = False
            btn_action.text = t("btn_process")
            btn_action.icon = ft.icons.PLAY_ARROW
            btn_action.bgcolor = COLOR_PRIMARY
            btn_action.update()
            lbl_status.update()