from collections.abc import Callable
from pathlib import Path

import flet as ft

from ui.components.tool_page import build_tool_page
from ui.controllers.video_downscale_controller import (
    SUPPORTED_VIDEO_DOWNSCALE_PRESETS,
    VideoDownscaleController,
)
from ui.i18n import t
from ui.utils.format_utils import video_input_formats

_PRESET_LABEL_KEYS: dict[str, str] = {
    "1080p": "preset_resolution_1080p",
    "720p": "preset_resolution_720p",
    "480p": "preset_resolution_480p",
}


def create_video_downscale_page(
    page: ft.Page,
    _selected_paths: dict[str, Path],
    _on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds the video downscale page."""
    default_preset = SUPPORTED_VIDEO_DOWNSCALE_PRESETS[0]
    dd_resolution = ft.Dropdown(
        label=t("lbl_target_resolution"),
        value=default_preset,
        width=385,
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
    )
