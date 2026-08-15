from pathlib import Path
from typing import Callable, Dict
import flet as ft

from ui.components.io_picker_card import create_clickable_card
from ui.controllers.video_conversion_controller import (
    SUPPORTED_VIDEO_CONVERSION_FORMATS,
    VideoConversionController,
)
from ui.i18n import t
from ui.theme import (
    BUTTON_HEIGHT,
    COLOR_CARD_BG,
    COLOR_PRIMARY,
    COLOR_SUBTEXT,
    COLOR_TEXT,
    FORM_WIDTH,
)


def create_video_conversion_page(
    page: ft.Page,
    selected_paths: Dict[str, Path],
    on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds unified video conversion page layout referencing i18n keys."""
    controller = VideoConversionController()

    lbl_in_path = ft.Text(
        t("lbl_not_selected"),
        size=11,
        color=COLOR_SUBTEXT,
        overflow=ft.TextOverflow.ELLIPSIS,
        max_lines=1,
    )
    lbl_out_path = ft.Text(
        t("lbl_not_selected"),
        size=11,
        color=COLOR_SUBTEXT,
        overflow=ft.TextOverflow.ELLIPSIS,
        max_lines=1,
    )
    lbl_status = ft.Text("", size=13, weight=ft.FontWeight.W_600)
    progress_bar = ft.ProgressBar(width=FORM_WIDTH, value=0, visible=False)

    # Setup target format dropdown control
    dd_format = ft.Dropdown(
        label=t("lbl_target_format"),
        value=SUPPORTED_VIDEO_CONVERSION_FORMATS[0].upper(),
        width=385,
        options=[
            ft.dropdown.Option(fmt.upper())
            for fmt in SUPPORTED_VIDEO_CONVERSION_FORMATS
        ],
    )

    # Initialize FilePickers for input and output selection
    picker_in_file = ft.FilePicker(
        on_result=lambda e: controller.handle_input_result(e, lbl_in_path)
    )
    picker_in_dir = ft.FilePicker(
        on_result=lambda e: controller.handle_input_result(e, lbl_in_path)
    )
    picker_out = ft.FilePicker(
        on_result=lambda e: controller.handle_output_result(e, lbl_out_path)
    )

    for p in (picker_in_file, picker_in_dir, picker_out):
        if p not in page.overlay:
            page.overlay.append(p)

    # Source selection card with popup menu
    card_in = ft.Container(
        width=185,
        height=125,
        bgcolor=COLOR_CARD_BG,
        border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
        border_radius=12,
        padding=10,
        ink=True,
        content=ft.PopupMenuButton(
            content=ft.Column(
                [
                    ft.Icon(ft.icons.FOLDER_OPEN, size=28, color=COLOR_PRIMARY),
                    ft.Text(
                        t("lbl_source"),
                        size=12,
                        weight=ft.FontWeight.W_600,
                        color=COLOR_TEXT,
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
                    icon=ft.icons.VIDEO_FILE,
                    text=t("lbl_select_file"),
                    on_click=lambda _: controller.open_picker(
                        picker_in_file, allow_directory=False
                    ),
                ),
                ft.PopupMenuItem(
                    icon=ft.icons.FOLDER,
                    text=t("lbl_select_folder"),
                    on_click=lambda _: controller.open_picker(
                        picker_in_dir, allow_directory=True
                    ),
                ),
            ],
        ),
    )

    # Destination directory card
    card_out = create_clickable_card(
        title=t("lbl_destination"),
        icon=ft.icons.FOLDER,
        lbl_text=lbl_out_path,
        on_click_action=lambda _: controller.open_picker(
            picker_out, allow_directory=True
        ),
    )

    btn_action = ft.ElevatedButton(
        t("btn_process"),
        icon=ft.icons.PLAY_ARROW,
        bgcolor=COLOR_PRIMARY,
        color=COLOR_TEXT,
        width=FORM_WIDTH,
        height=BUTTON_HEIGHT,
    )

    btn_action.on_click = lambda _: controller.handle_action_click(
        page=page,
        target_format=dd_format.value,
        lbl_status=lbl_status,
        progress_bar=progress_bar,
        btn_action=btn_action,
    )

    return ft.Container(
        expand=True,
        alignment=ft.alignment.center,
        padding=20,
        content=ft.Container(
            width=FORM_WIDTH,
            padding=25,
            bgcolor=COLOR_CARD_BG,
            border_radius=12,
            content=ft.Column(
                [
                    ft.Text(
                        t("video_hub_card_conversion_title"),
                        size=20,
                        weight=ft.FontWeight.W_600,
                        color=COLOR_TEXT,
                    ),
                    ft.Divider(height=15, color=COLOR_SUBTEXT),
                    ft.Row(
                        [card_in, card_out],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=15,
                        wrap=True,
                    ),
                    dd_format,
                    ft.Container(height=5),
                    progress_bar,
                    btn_action,
                    lbl_status,
                ],
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ),
    )