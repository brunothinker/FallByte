from collections.abc import Callable
from pathlib import Path

import flet as ft

from ui.components.quality_selector import QualitySelector
from ui.components.tool_page import build_tool_page
from ui.controllers.audio_compression_controller import AudioCompressionController
from ui.i18n import t
from ui.utils.format_utils import audio_compression_formats


def create_audio_compression_page(
    page: ft.Page,
    _selected_paths: dict[str, Path],
    _on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds the audio compression page."""
    quality_selector = QualitySelector(
        initial_value=80, label_text=t("lbl_quality_title")
    )

    return build_tool_page(
        page=page,
        controller=AudioCompressionController(),
        title_key="audio_hub_card_compression_title",
        formats=audio_compression_formats(),
        file_icon=ft.icons.AUDIO_FILE,
        extra_controls=[quality_selector],
        get_params=quality_selector.get_value,
    )
