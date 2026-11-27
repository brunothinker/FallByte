from collections.abc import Callable
from typing import Any

import flet as ft

from ui.components.quality_selector import QualitySelector
from ui.components.tool_page import build_tool_page
from ui.controllers.image_compression_controller import (
    CompressionController,
    CompressionOptions,
)
from ui.i18n import t
from ui.theme import get_color
from ui.utils.compression_utils import validate_quality_value
from ui.utils.format_utils import image_compression_formats

ROUTE_KEY = "image_compression"


def create_compression_page(
    page: ft.Page,
    selected_paths: dict[str, Any],
    _on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds the image compression page."""
    saved_opts = (selected_paths.get(ROUTE_KEY) or {}).get("options") or {}
    initial_quality = validate_quality_value(saved_opts.get("quality", 80), default=80)
    initial_strip = bool(saved_opts.get("strip_metadata", False))

    quality_selector = QualitySelector(
        initial_value=initial_quality, label_text=t("lbl_quality_title")
    )

    chk_strip_metadata = ft.Checkbox(
        label=t("lbl_strip_metadata"),
        value=initial_strip,
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
        selected_paths=selected_paths,
        route_key=ROUTE_KEY,
        get_state=lambda: {
            "quality": quality_selector.get_value(),
            "strip_metadata": bool(chk_strip_metadata.value),
        },
    )
