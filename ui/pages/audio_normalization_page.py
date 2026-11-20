from collections.abc import Callable
from pathlib import Path

import flet as ft

from src.audio.audio_file_normalization import DEFAULT_LOUDNESS_PRESET
from ui.components.io_picker_card import create_clickable_card
from ui.components.path_label import create_path_label
from ui.controllers.audio_normalization_controller import (
    AudioNormalizationController,
    normalizable_audio_formats,
)
from ui.i18n import t
from ui.theme import (
    BUTTON_HEIGHT,
    FORM_WIDTH,
    get_color,
)
from ui.utils.format_utils import format_list


def create_audio_normalization_page(
    page: ft.Page,
    _selected_paths: dict[str, Path],
    on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds batch audio loudness normalization page layout referencing i18n keys."""
    controller = AudioNormalizationController()

    lbl_in_path = create_path_label()
    lbl_out_path = create_path_label()
    lbl_status = ft.Text("", size=13, weight=ft.FontWeight.W_600)
    progress_bar = ft.ProgressBar(width=FORM_WIDTH, value=0, visible=False)

    dd_preset = ft.Dropdown(
        label=t("lbl_loudness_preset"),
        value=DEFAULT_LOUDNESS_PRESET,
        width=385,
        options=[
            ft.dropdown.Option(key="music", text=t("preset_loudness_music")),
            ft.dropdown.Option(key="podcast", text=t("preset_loudness_podcast")),
            ft.dropdown.Option(key="broadcast", text=t("preset_loudness_broadcast")),
        ],
    )

    picker_in_dir = ft.FilePicker(
        on_result=lambda e: controller.handle_input_result(e, lbl_in_path, lbl_status)
    )
    picker_out = ft.FilePicker(
        on_result=lambda e: controller.handle_output_result(e, lbl_out_path, lbl_status)
    )

    for p in (picker_in_dir, picker_out):
        if p not in page.overlay:
            page.overlay.append(p)

    card_in = create_clickable_card(
        title=t("lbl_source"),
        icon=ft.icons.FOLDER_OPEN,
        lbl_text=lbl_in_path,
        on_click_action=lambda _: controller.open_picker(
            picker_in_dir, allow_directory=True
        ),
    )

    card_out = create_clickable_card(
        title=t("lbl_destination"),
        icon=ft.icons.FOLDER,
        lbl_text=lbl_out_path,
        on_click_action=lambda _: controller.open_picker(
            picker_out, allow_directory=True, is_output=True
        ),
    )

    btn_action = ft.ElevatedButton(
        t("btn_process"),
        icon=ft.icons.PLAY_ARROW,
        bgcolor=get_color("primary"),
        color=get_color("text"),
        width=FORM_WIDTH,
        height=BUTTON_HEIGHT,
    )

    lbl_notice = ft.Text(
        t(
            "msg_supported_formats_notice_normalization",
            formats=format_list(normalizable_audio_formats()),
        ),
        size=11,
        color=get_color("subtext"),
        text_align=ft.TextAlign.CENTER,
    )

    def on_action_click(_: ft.ControlEvent) -> None:
        """Handles action button clicks forwarding preset and state to controller."""
        controller.handle_action_click(
            page=page,
            preset_key=dd_preset.value or DEFAULT_LOUDNESS_PRESET,
            lbl_status=lbl_status,
            progress_bar=progress_bar,
            btn_action=btn_action,
        )

    btn_action.on_click = on_action_click

    return ft.Container(
        expand=True,
        alignment=ft.alignment.center,
        padding=20,
        content=ft.Container(
            width=FORM_WIDTH,
            padding=25,
            bgcolor=get_color("card_bg"),
            border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
            border_radius=12,
            content=ft.Column(
                [
                    ft.Text(
                        t("audio_hub_card_normalization_title"),
                        size=20,
                        weight=ft.FontWeight.W_600,
                        color=get_color("text"),
                    ),
                    ft.Divider(height=15, color=get_color("subtext")),
                    ft.Row(
                        [card_in, card_out],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=15,
                        wrap=True,
                    ),
                    dd_preset,
                    ft.Container(height=5),
                    progress_bar,
                    btn_action,
                    lbl_notice,
                    lbl_status,
                ],
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ),
    )
