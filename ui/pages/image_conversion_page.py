from collections.abc import Callable
from pathlib import Path

import flet as ft

from ui.components.tool_page import build_tool_page
from ui.controllers.image_conversion_controller import (
    ConversionController,
    ConversionOptions,
)
from ui.i18n import t
from ui.theme import get_color
from ui.utils.conversion_utils import (
    SUPPORTED_CONVERSION_FORMATS,
    get_color_options,
)
from ui.utils.format_utils import image_input_formats


def create_conversion_page(
    page: ft.Page,
    _selected_paths: dict[str, Path],
    _on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds the image conversion page."""
    dd_format = ft.Dropdown(
        label=t("lbl_target_format"),
        value=SUPPORTED_CONVERSION_FORMATS[0],
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
        options=[ft.dropdown.Option(fmt) for fmt in SUPPORTED_CONVERSION_FORMATS],
    )

    color_options = get_color_options()
    dd_color = ft.Dropdown(
        label=t("lbl_transparency_color"),
        value=color_options[0][0],
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
        options=[ft.dropdown.Option(key, text=label) for key, label in color_options],
    )

    return build_tool_page(
        page=page,
        controller=ConversionController(),
        title_key="image_hub_card_conversion_title",
        formats=image_input_formats(),
        notice_key="msg_supported_formats_notice_conversion",
        extra_controls=[dd_format, dd_color],
        get_params=lambda: ConversionOptions(
            target_format=dd_format.value or SUPPORTED_CONVERSION_FORMATS[0],
            color_key=dd_color.value or color_options[0][0],
        ),
    )
