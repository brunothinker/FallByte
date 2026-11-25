from collections.abc import Callable
from pathlib import Path
from typing import Any

import flet as ft

from ui.components.tool_page import build_tool_page
from ui.controllers.video_compression_controller import VideoCompressionController
from ui.i18n import t
from ui.theme import get_color
from ui.utils.format_utils import video_input_formats


def create_video_compression_page(
    page: ft.Page,
    _selected_paths: dict[str, Path],
    _on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds the video compression page with an interactive quality slider."""
    lbl_quality_val = ft.Text(
        t("lbl_quality_percentage", value=80),
        size=14,
        weight=ft.FontWeight.W_600,
        color=get_color("text"),
    )

    def on_slider_change(e: Any) -> None:
        """Updates quality display label upon slider changes."""
        raw_val = e.control.value if e.control.value is not None else 80
        lbl_quality_val.value = t("lbl_quality_percentage", value=int(raw_val))
        lbl_quality_val.update()

    slider_quality = ft.Slider(
        min=1,
        max=100,
        divisions=99,
        value=80,
        label="{value}%",
        active_color=get_color("primary"),
        on_change=on_slider_change,
    )

    quality_container = ft.Column(
        [
            ft.Row(
                [
                    ft.Text(
                        t("lbl_quality_title"),
                        size=13,
                        weight=ft.FontWeight.W_500,
                        color=get_color("text"),
                    ),
                    lbl_quality_val,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            slider_quality,
        ],
        spacing=2,
    )

    return build_tool_page(
        page=page,
        controller=VideoCompressionController(),
        title_key="video_hub_card_compression_title",
        formats=video_input_formats(),
        file_icon=ft.Icons.VIDEO_FILE,
        extra_controls=[ft.Container(height=5), quality_container],
        get_params=lambda: int(
            slider_quality.value if slider_quality.value is not None else 80
        ),
    )
