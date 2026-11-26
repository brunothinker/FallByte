from collections.abc import Callable
from pathlib import Path

import flet as ft

from ui.components.quality_selector import QualitySelector
from ui.components.tool_page import build_tool_page
from ui.controllers.video_compression_controller import VideoCompressionController
from ui.i18n import t
from ui.utils.format_utils import video_input_formats


def create_video_compression_page(
    page: ft.Page,
    _selected_paths: dict[str, Path],
    _on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds the video compression page with an interactive quality selector."""
    quality_selector = QualitySelector(
        initial_value=80, label_text=t("lbl_quality_title")
    )

    return build_tool_page(
        page=page,
        controller=VideoCompressionController(),
        title_key="video_hub_card_compression_title",
        formats=video_input_formats(),
        file_icon=ft.Icons.VIDEO_FILE,
        extra_controls=[quality_selector],
        get_params=quality_selector.get_value,
    )
