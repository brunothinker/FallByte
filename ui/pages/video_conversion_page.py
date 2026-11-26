from collections.abc import Callable
from pathlib import Path

import flet as ft

from ui.components.tool_page import build_tool_page
from ui.controllers.video_conversion_controller import (
    SUPPORTED_VIDEO_CONVERSION_FORMATS,
    VideoConversionController,
)
from ui.i18n import t
from ui.theme import get_color
from ui.utils.format_utils import video_input_formats


def create_video_conversion_page(
    page: ft.Page,
    _selected_paths: dict[str, Path],
    _on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds the video conversion page."""
    default_format = SUPPORTED_VIDEO_CONVERSION_FORMATS[0].upper()
    dd_format = ft.Dropdown(
        label=t("lbl_target_format"),
        value=default_format,
        width=385,
        filled=True,
        bgcolor=get_color("card_bg"),
        fill_color=get_color("card_bg"),
        menu_style=ft.MenuStyle(
            bgcolor=get_color("card_bg"),
            side=ft.BorderSide(1, get_color("primary")),
        ),
        border_color=ft.Colors.with_opacity(0.45, get_color("primary")),
        border_width=1,
        focused_border_color=get_color("primary"),
        focused_border_width=1.5,
        options=[
            ft.dropdown.Option(fmt.upper())
            for fmt in SUPPORTED_VIDEO_CONVERSION_FORMATS
        ],
    )

    return build_tool_page(
        page=page,
        controller=VideoConversionController(),
        title_key="video_hub_card_conversion_title",
        formats=video_input_formats(),
        notice_key="msg_supported_formats_notice_conversion",
        file_icon=ft.Icons.VIDEO_FILE,
        extra_controls=[dd_format],
        get_params=lambda: dd_format.value or default_format,
    )
