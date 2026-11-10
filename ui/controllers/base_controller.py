from pathlib import Path

import flet as ft

from ui.i18n import t
from ui.theme import get_color
from ui.utils.path_utils import get_safe_initial_directory


class BaseController:
    """Base controller providing common state attributes, UI state transitions, and file picker handlers."""

    def __init__(self) -> None:
        """Initializes state variables shared across UI controllers."""
        self.selected_input: Path | None = None
        self.selected_output_dir: Path | None = None
        self.is_processing: bool = False
        self.abort_requested: bool = False
        self.picker_active: bool = False
        self.cancel_dialog: ft.AlertDialog | None = None

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
            lbl_path.value = (
                self.selected_input.name or str(self.selected_input)
            )
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
            lbl_path.value = (
                self.selected_output_dir.name or str(self.selected_output_dir)
            )
            lbl_path.color = get_color("text")
            lbl_path.update()

            if lbl_status:
                lbl_status.value = ""
                lbl_status.update()

    def _set_processing_ui(
        self,
        page: ft.Page,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Transitions UI controls and session flags to active processing state."""
        self.is_processing = True
        self.abort_requested = False
        page.session.set("is_processing", True)

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
        self.is_processing = False
        self.abort_requested = False
        page.session.set("is_processing", False)

        progress_bar.visible = False
        progress_bar.update()

        btn_action.text = t("btn_process")
        btn_action.icon = ft.icons.PLAY_ARROW
        btn_action.bgcolor = get_color("primary")
        btn_action.color = get_color("text")
        btn_action.update()

    def _close_cancel_dialog(self, page: ft.Page) -> None:
        """Closes and unmounts active processing cancellation dialog."""
        if self.cancel_dialog:
            self.cancel_dialog.open = False
            page.update()
            self.cancel_dialog = None

    def _on_cancel_confirmed(self) -> None:
        """Hook method invoked when process cancellation is confirmed by user.
        
        Subclasses (e.g. video controllers) override this to signal thread/process events.
        """

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