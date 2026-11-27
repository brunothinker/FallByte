from collections.abc import Callable
from typing import Any

import flet as ft

from ui.components.tool_page import build_tool_page
from ui.controllers.video_conversion_controller import (
    SUPPORTED_VIDEO_CONVERSION_FORMATS,
    VideoConversionController,
)
from ui.i18n import t
from ui.theme import get_color
from ui.utils.format_utils import video_input_formats

ROUTE_KEY = "video_conversion"


def create_video_conversion_page(
    page: ft.Page,
    selected_paths: dict[str, Any],
    _on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds the video conversion page."""
    saved_opts = (selected_paths.get(ROUTE_KEY) or {}).get("options") or {}
    valid_formats = [fmt.upper() for fmt in SUPPORTED_VIDEO_CONVERSION_FORMATS]
    default_format = valid_formats[0]

    initial_fmt = saved_opts.get("target_format")
    if initial_fmt not in valid_formats:
        initial_fmt = default_format

    dd_format = ft.Dropdown(
        label=t("lbl_target_format"),
        value=initial_fmt,
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
        options=[ft.dropdown.Option(fmt) for fmt in valid_formats],
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
        selected_paths=selected_paths,
        route_key=ROUTE_KEY,
        get_state=lambda: {"target_format": dd_format.value or default_format},
    )
