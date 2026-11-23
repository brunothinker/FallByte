from collections.abc import Callable
from pathlib import Path

import flet as ft

from ui.components.tool_page import build_tool_page
from ui.controllers.image_metadata_controller import ImageMetadataController
from ui.i18n import t
from ui.theme import get_color
from ui.utils.format_utils import image_input_formats


def create_image_metadata_page(
    page: ft.Page,
    _selected_paths: dict[str, Path],
    _on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds the image metadata removal page."""
    privacy_hint = ft.Text(
        t("msg_metadata_privacy_hint"),
        size=12,
        color=get_color("subtext"),
        text_align=ft.TextAlign.CENTER,
    )

    return build_tool_page(
        page=page,
        controller=ImageMetadataController(),
        title_key="image_hub_card_metadata_title",
        formats=image_input_formats(),
        notice_key="msg_supported_formats_notice_metadata",
        extra_controls=[privacy_hint],
    )
