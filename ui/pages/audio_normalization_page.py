from collections.abc import Callable
from pathlib import Path

import flet as ft

from src.audio.audio_file_normalization import DEFAULT_LOUDNESS_PRESET
from ui.components.tool_page import build_tool_page
from ui.controllers.audio_normalization_controller import (
    AudioNormalizationController,
    normalizable_audio_formats,
)
from ui.i18n import t


def create_audio_normalization_page(
    page: ft.Page,
    _selected_paths: dict[str, Path],
    _on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds the batch audio loudness normalization page (folder input only)."""
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

    return build_tool_page(
        page=page,
        controller=AudioNormalizationController(),
        title_key="audio_hub_card_normalization_title",
        formats=normalizable_audio_formats(),
        notice_key="msg_supported_formats_notice_normalization",
        source_mode="folder",
        extra_controls=[dd_preset],
        get_params=lambda: dd_preset.value or DEFAULT_LOUDNESS_PRESET,
    )
