from collections.abc import Callable
from typing import Any

import flet as ft

from ui.components.tool_page import build_tool_page
from ui.controllers.video_downscale_controller import (
    SUPPORTED_VIDEO_DOWNSCALE_PRESETS,
    VideoDownscaleController,
)
from ui.i18n import t
from ui.theme import get_color
from ui.utils.format_utils import video_input_formats

ROUTE_KEY = "video_downscale"

_PRESET_LABEL_KEYS: dict[str, str] = {
    "1080p": "preset_resolution_1080p",
    "720p": "preset_resolution_720p",
    "480p": "preset_resolution_480p",
}


def create_video_downscale_page(
    page: ft.Page,
    selected_paths: dict[str, Any],
    _on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds the video downscale page."""
    saved_opts = (selected_paths.get(ROUTE_KEY) or {}).get("options") or {}
    default_preset = SUPPORTED_VIDEO_DOWNSCALE_PRESETS[0]
    initial_preset = saved_opts.get("resolution")
    if initial_preset not in SUPPORTED_VIDEO_DOWNSCALE_PRESETS:
        initial_preset = default_preset

    dd_resolution = ft.Dropdown(
        label=t("lbl_target_resolution"),
        value=initial_preset,
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
            ft.dropdown.Option(key=preset, text=t(_PRESET_LABEL_KEYS[preset]))
            for preset in SUPPORTED_VIDEO_DOWNSCALE_PRESETS
        ],
    )

    return build_tool_page(
        page=page,
        controller=VideoDownscaleController(),
        title_key="video_hub_card_downscale_title",
        formats=video_input_formats(),
        notice_key="msg_supported_formats_notice_downscale",
        file_icon=ft.Icons.VIDEO_FILE,
        extra_controls=[dd_resolution],
        get_params=lambda: dd_resolution.value or default_preset,
        selected_paths=selected_paths,
        route_key=ROUTE_KEY,
        get_state=lambda: {"resolution": dd_resolution.value or default_preset},
    )
