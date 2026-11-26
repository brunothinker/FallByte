from collections.abc import Callable
from pathlib import Path

import flet as ft

from ui.components.quality_selector import QualitySelector
from ui.components.tool_page import build_tool_page
from ui.controllers.image_compression_controller import (
    CompressionController,
    CompressionOptions,
)
from ui.i18n import t
from ui.theme import get_color
from ui.utils.format_utils import image_compression_formats


def create_compression_page(
    page: ft.Page,
    _selected_paths: dict[str, Path],
    _on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds the image compression page."""
    quality_selector = QualitySelector(
        initial_value=80, label_text=t("lbl_quality_title")
    )

    chk_strip_metadata = ft.Checkbox(
        label=t("lbl_strip_metadata"),
        value=False,
        active_color=get_color("primary"),
        check_color="#FFFFFF",
        tooltip=t("tooltip_strip_metadata"),
    )

    return build_tool_page(
        page=page,
        controller=CompressionController(),
        title_key="image_hub_card_compression_title",
        formats=image_compression_formats(),
        extra_controls=[quality_selector, chk_strip_metadata],
        get_params=lambda: CompressionOptions(
            quality=quality_selector.get_value(),
            strip_metadata=bool(chk_strip_metadata.value),
        ),
    )
