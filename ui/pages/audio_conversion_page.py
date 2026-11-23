from collections.abc import Callable
from pathlib import Path

import flet as ft

from ui.components.tool_page import build_tool_page
from ui.controllers.audio_conversion_controller import AudioConversionController
from ui.i18n import t
from ui.utils.format_utils import audio_input_formats, audio_output_formats


def create_audio_conversion_page(
    page: ft.Page,
    _selected_paths: dict[str, Path],
    _on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds the audio conversion page."""
    output_formats = audio_output_formats()
    dd_format = ft.Dropdown(
        label=t("lbl_target_format"),
        value=output_formats[0],
        width=385,
        options=[ft.dropdown.Option(fmt) for fmt in output_formats],
    )

    return build_tool_page(
        page=page,
        controller=AudioConversionController(),
        title_key="audio_hub_card_conversion_title",
        formats=audio_input_formats(),
        notice_key="msg_supported_formats_notice_conversion",
        file_icon=ft.icons.AUDIO_FILE,
        extra_controls=[dd_format],
        get_params=lambda: dd_format.value or output_formats[0],
    )
