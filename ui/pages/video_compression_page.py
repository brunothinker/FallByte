from collections.abc import Callable
from typing import Any

import flet as ft

from ui.components.quality_selector import QualitySelector
from ui.components.tool_page import build_tool_page
from ui.controllers.video_compression_controller import VideoCompressionController
from ui.i18n import t
from ui.utils.compression_utils import validate_quality_value
from ui.utils.format_utils import video_input_formats

ROUTE_KEY = "video_compression"


def create_video_compression_page(
    page: ft.Page,
    selected_paths: dict[str, Any],
    _on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds the video compression page with an interactive quality selector."""
    saved_opts = (selected_paths.get(ROUTE_KEY) or {}).get("options") or {}
    initial_quality = validate_quality_value(saved_opts.get("quality", 80), default=80)

    quality_selector = QualitySelector(
        initial_value=initial_quality, label_text=t("lbl_quality_title")
    )

    return build_tool_page(
        page=page,
        controller=VideoCompressionController(),
        title_key="video_hub_card_compression_title",
        formats=video_input_formats(),
        file_icon=ft.Icons.VIDEO_FILE,
        extra_controls=[quality_selector],
        get_params=quality_selector.get_value,
        selected_paths=selected_paths,
        route_key=ROUTE_KEY,
        get_state=lambda: {"quality": quality_selector.get_value()},
    )
