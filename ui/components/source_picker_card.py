from collections.abc import Callable

import flet as ft

from ui.i18n import t
from ui.theme import get_color


def create_source_picker_card(
    lbl_in_path: ft.Text,
    on_select_file: Callable[[], None],
    on_select_folder: Callable[[], None],
    file_icon: str = ft.icons.UPLOAD_FILE,
) -> ft.Container:
    """Constructs a source selection card containing a PopupMenuButton to pick files or folders.

    Args:
        lbl_in_path (ft.Text): UI text component rendering the input path status.
        on_select_file (Callable[[], None]): Callback invoked when 'Select File' is clicked.
        on_select_folder (Callable[[], None]): Callback invoked when 'Select Folder' is clicked.
        file_icon (str, optional): Flet icon string for the file menu item. Defaults to ft.icons.UPLOAD_FILE.

    Returns:
        ft.Container: Configured clickable source selection card UI component.
    """
    return ft.Container(
        width=185,
        height=125,
        bgcolor=get_color("card_bg"),
        border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
        border_radius=12,
        padding=10,
        ink=True,
        content=ft.PopupMenuButton(
            content=ft.Column(
                [
                    ft.Icon(ft.icons.FOLDER_OPEN, size=28, color=get_color("primary")),
                    ft.Text(
                        t("lbl_source"),
                        size=12,
                        weight=ft.FontWeight.W_600,
                        color=get_color("text"),
                        text_align=ft.TextAlign.CENTER,
                    ),
                    lbl_in_path,
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
            items=[
                ft.PopupMenuItem(
                    icon=file_icon,
                    text=t("lbl_select_file"),
                    on_click=lambda _: on_select_file(),
                ),
                ft.PopupMenuItem(
                    icon=ft.icons.FOLDER,
                    text=t("lbl_select_folder"),
                    on_click=lambda _: on_select_folder(),
                ),
            ],
        ),
    )