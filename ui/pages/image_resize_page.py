from collections.abc import Callable
from pathlib import Path

import flet as ft

from ui.components.tool_page import build_tool_page
from ui.controllers.image_resize_controller import (
    ImageResizeController,
    ResizeOptions,
)
from ui.i18n import t
from ui.utils.format_utils import image_input_formats


def _parse_positive_int(raw: str | None) -> int | None:
    """Parses a stripped text field value into a positive integer or None."""
    if not raw or not raw.strip():
        return None
    try:
        value = int(raw.strip())
        return value if value > 0 else None
    except ValueError:
        return None


def create_image_resize_page(
    page: ft.Page,
    _selected_paths: dict[str, Path],
    _on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds the image resize page (dimension/percentage mode switch)."""
    dd_mode = ft.Dropdown(
        label=t("lbl_resize_mode"),
        value="dimension",
        width=385,
        options=[
            ft.dropdown.Option(key="dimension", text=t("resize_mode_dimension")),
            ft.dropdown.Option(key="percentage", text=t("resize_mode_percentage")),
        ],
    )

    txt_max_width = ft.TextField(
        label=t("lbl_max_width"),
        value="1920",
        width=185,
        suffix_text="px",
        keyboard_type=ft.KeyboardType.NUMBER,
    )
    txt_max_height = ft.TextField(
        label=t("lbl_max_height"),
        value="1080",
        width=185,
        suffix_text="px",
        keyboard_type=ft.KeyboardType.NUMBER,
    )
    dimension_row = ft.Row(
        [txt_max_width, txt_max_height],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=15,
        visible=True,
    )
    txt_percentage = ft.TextField(
        label=t("lbl_scale_percentage"),
        value="50",
        width=385,
        suffix_text="%",
        keyboard_type=ft.KeyboardType.NUMBER,
        visible=False,
    )

    def on_mode_change(_: ft.ControlEvent) -> None:
        is_dimension = (dd_mode.value or "dimension") == "dimension"
        dimension_row.visible = is_dimension
        txt_percentage.visible = not is_dimension
        page.update()

    dd_mode.on_change = on_mode_change

    def collect_options() -> ResizeOptions:
        mode = dd_mode.value or "dimension"
        if mode == "dimension":
            return ResizeOptions(
                mode=mode,
                max_width=_parse_positive_int(txt_max_width.value),
                max_height=_parse_positive_int(txt_max_height.value),
                percentage=None,
            )
        return ResizeOptions(
            mode=mode,
            max_width=None,
            max_height=None,
            percentage=_parse_positive_int(txt_percentage.value),
        )

    return build_tool_page(
        page=page,
        controller=ImageResizeController(),
        title_key="image_hub_card_resize_title",
        formats=image_input_formats(),
        notice_key="msg_supported_formats_notice_resize",
        extra_controls=[dd_mode, dimension_row, txt_percentage],
        get_params=collect_options,
    )
