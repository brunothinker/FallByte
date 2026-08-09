from pathlib import Path
from typing import Callable, Dict
import flet as ft

from ui.controllers.images.compression.compression_controllers import (
    CompressionDirController,
    CompressionFileController,
)
from ui.i18n import t
from ui.theme import (
    COLOR_CARD_BG,
    COLOR_PRIMARY,
    COLOR_SUBTEXT,
    COLOR_TEXT,
    FORM_WIDTH,
    BUTTON_HEIGHT,
)


def create_clickable_card(
    title: str,
    icon: str,
    lbl_text: ft.Text,
    on_click_action: Callable
) -> ft.Container:
    """Creates a responsive card container for direct file or directory selection."""
    return ft.Container(
        width=185,
        height=125,
        bgcolor=COLOR_CARD_BG,
        border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
        border_radius=12,
        padding=10,
        ink=True,
        on_click=on_click_action,
        content=ft.Column([
            ft.Icon(icon, size=28, color=COLOR_PRIMARY),
            ft.Text(title, size=12, weight=ft.FontWeight.W_600, color=COLOR_TEXT, text_align=ft.TextAlign.CENTER),
            lbl_text
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4)
    )


def create_compression_dir_page(
    page: ft.Page,
    selected_paths: Dict[str, Path],
    on_navigate: Callable[[str], None]
) -> ft.Container:
    controller = CompressionDirController()

    lbl_in_path = ft.Text(t("lbl_not_selected"), size=11, color=COLOR_SUBTEXT, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1)
    lbl_out_path = ft.Text(t("lbl_not_selected"), size=11, color=COLOR_SUBTEXT, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1)
    lbl_status = ft.Text("", size=13, weight=ft.FontWeight.W_600)
    progress_bar = ft.ProgressBar(width=FORM_WIDTH, value=0, visible=False)

    slider_quality = ft.Slider(
        min=1, max=100, divisions=100, value=80, expand=True
    )

    txt_quality = ft.TextField(
        value="80", width=75, height=40,
        text_align=ft.TextAlign.CENTER,
        content_padding=ft.padding.symmetric(vertical=0, horizontal=5),
        suffix_text="%", keyboard_type=ft.KeyboardType.NUMBER
    )

    slider_quality.on_change = lambda e: controller.sync_from_slider(e, txt_quality)
    txt_quality.on_change = lambda e: controller.sync_from_text(e, slider_quality)
    txt_quality.on_blur = lambda e: controller.validate_text_blur(e, slider_quality, txt_quality)

    picker_in = ft.FilePicker(on_result=lambda e: controller.handle_in_dir_result(e, lbl_in_path))
    picker_out = ft.FilePicker(on_result=lambda e: controller.handle_out_dir_result(e, lbl_out_path))

    if picker_in not in page.overlay:
        page.overlay.append(picker_in)
    if picker_out not in page.overlay:
        page.overlay.append(picker_out)

    card_in = create_clickable_card(
        title=t("lbl_select_input_dir"),
        icon=ft.icons.FOLDER_OPEN,
        lbl_text=lbl_in_path,
        on_click_action=lambda _: controller.open_dir_picker(picker_in)
    )

    card_out = create_clickable_card(
        title=t("lbl_select_output_dir"),
        icon=ft.icons.FOLDER,
        lbl_text=lbl_out_path,
        on_click_action=lambda _: controller.open_dir_picker(picker_out)
    )

    btn_action = ft.ElevatedButton(
        t("btn_process"),
        icon=ft.icons.PLAY_ARROW,
        bgcolor=COLOR_PRIMARY,
        color=COLOR_TEXT,
        width=FORM_WIDTH,
        height=BUTTON_HEIGHT
    )

    btn_action.on_click = lambda _: controller.handle_action_click(
        page=page,
        quality=int(slider_quality.value),
        lbl_status=lbl_status,
        progress_bar=progress_bar,
        btn_action=btn_action
    )

    return ft.Container(
        alignment=ft.alignment.center,
        padding=20,
        content=ft.Container(
            width=FORM_WIDTH,
            padding=25,
            bgcolor=COLOR_CARD_BG,
            border_radius=12,
            content=ft.Column([
                ft.Text(t("form_compression_dir_title"), size=20, weight=ft.FontWeight.W_600, color=COLOR_TEXT),
                ft.Divider(height=15, color=COLOR_SUBTEXT),

                ft.Row(
                    [card_in, card_out],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=15
                ),

                ft.Column([
                    ft.Text("Qualidade da Compressão", size=13, color=COLOR_TEXT, weight=ft.FontWeight.W_600),
                    ft.Row([
                        slider_quality,
                        txt_quality,
                    ], alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                ], spacing=5),

                ft.Container(height=5),
                progress_bar,
                btn_action,
                lbl_status,
            ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )
    )


def create_compression_file_page(
    page: ft.Page,
    selected_paths: Dict[str, Path],
    on_navigate: Callable[[str], None]
) -> ft.Container:
    controller = CompressionFileController()

    lbl_file_path = ft.Text(t("lbl_not_selected"), size=11, color=COLOR_SUBTEXT, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1)
    lbl_out_path = ft.Text(t("lbl_not_selected"), size=11, color=COLOR_SUBTEXT, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1)
    lbl_status = ft.Text("", size=13, weight=ft.FontWeight.W_600)

    slider_quality = ft.Slider(
        min=1, max=100, divisions=100, value=80, expand=True
    )

    txt_quality = ft.TextField(
        value="80", width=75, height=40,
        text_align=ft.TextAlign.CENTER,
        content_padding=ft.padding.symmetric(vertical=0, horizontal=5),
        suffix_text="%", keyboard_type=ft.KeyboardType.NUMBER
    )

    slider_quality.on_change = lambda e: controller.sync_from_slider(e, txt_quality)
    txt_quality.on_change = lambda e: controller.sync_from_text(e, slider_quality)
    txt_quality.on_blur = lambda e: controller.validate_text_blur(e, slider_quality, txt_quality)

    picker_file = ft.FilePicker(on_result=lambda e: controller.handle_file_result(e, lbl_file_path))
    picker_dir = ft.FilePicker(on_result=lambda e: controller.handle_dir_result(e, lbl_out_path))

    if picker_file not in page.overlay:
        page.overlay.append(picker_file)
    if picker_dir not in page.overlay:
        page.overlay.append(picker_dir)

    card_file = create_clickable_card(
        title=t("lbl_select_file"),
        icon=ft.icons.UPLOAD_FILE,
        lbl_text=lbl_file_path,
        on_click_action=lambda _: controller.open_file_picker(picker_file)
    )

    card_out = create_clickable_card(
        title=t("lbl_select_output_dir"),
        icon=ft.icons.FOLDER,
        lbl_text=lbl_out_path,
        on_click_action=lambda _: controller.open_dir_picker(picker_dir)
    )

    return ft.Container(
        alignment=ft.alignment.center,
        padding=20,
        content=ft.Container(
            width=FORM_WIDTH,
            padding=25,
            bgcolor=COLOR_CARD_BG,
            border_radius=12,
            content=ft.Column([
                ft.Text(t("form_compression_file_title"), size=20, weight=ft.FontWeight.W_600, color=COLOR_TEXT),
                ft.Divider(height=15, color=COLOR_SUBTEXT),

                ft.Row(
                    [card_file, card_out],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=15
                ),

                ft.Column([
                    ft.Text("Qualidade da Compressão", size=13, color=COLOR_TEXT, weight=ft.FontWeight.W_600),
                    ft.Row([
                        slider_quality,
                        txt_quality,
                    ], alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                ], spacing=5),

                ft.Container(height=5),
                ft.ElevatedButton(
                    t("btn_process"),
                    icon=ft.icons.PLAY_ARROW,
                    bgcolor=COLOR_PRIMARY,
                    color=COLOR_TEXT,
                    on_click=lambda _: controller.execute_compression(
                        quality=int(slider_quality.value),
                        lbl_status=lbl_status
                    ),
                    width=FORM_WIDTH,
                    height=BUTTON_HEIGHT
                ),
                lbl_status,
            ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )
    )