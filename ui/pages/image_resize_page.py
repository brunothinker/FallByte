from collections.abc import Callable
from typing import Any

import flet as ft

from ui.components.tool_page import build_tool_page
from ui.controllers.image_resize_controller import (
    ImageResizeController,
    ResizeOptions,
)
from ui.i18n import t
from ui.theme import get_color
from ui.utils.format_utils import image_input_formats

ROUTE_KEY = "image_resize"


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
    selected_paths: dict[str, Any],
    _on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds the image resize page (dimension/percentage mode switch)."""
    saved_opts = (selected_paths.get(ROUTE_KEY) or {}).get("options") or {}
    initial_mode = saved_opts.get("mode")
    if initial_mode not in ("dimension", "percentage"):
        initial_mode = "dimension"

    is_dimension_initial = initial_mode == "dimension"

    dd_mode = ft.Dropdown(
        label=t("lbl_resize_mode"),
        value=initial_mode,
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
        options=[
            ft.dropdown.Option(key="dimension", text=t("resize_mode_dimension")),
            ft.dropdown.Option(key="percentage", text=t("resize_mode_percentage")),
        ],
    )

    txt_max_width = ft.TextField(
        label=t("lbl_max_width"),
        value=str(saved_opts.get("max_width", "1920")),
        width=185,
        filled=True,
        bgcolor=get_color("card_bg"),
        fill_color=get_color("card_bg"),
        focused_bgcolor=get_color("card_hover"),
        border_color=ft.Colors.with_opacity(0.45, get_color("primary")),
        border_width=1,
        focused_border_color=get_color("primary"),
        focused_border_width=1.5,
        suffix="px",
        keyboard_type=ft.KeyboardType.NUMBER,
    )
    txt_max_height = ft.TextField(
        label=t("lbl_max_height"),
        value=str(saved_opts.get("max_height", "1080")),
        width=185,
        filled=True,
        bgcolor=get_color("card_bg"),
        fill_color=get_color("card_bg"),
        focused_bgcolor=get_color("card_hover"),
        border_color=ft.Colors.with_opacity(0.45, get_color("primary")),
        border_width=1,
        focused_border_color=get_color("primary"),
        focused_border_width=1.5,
        suffix="px",
        keyboard_type=ft.KeyboardType.NUMBER,
    )
    dimension_row = ft.Row(
        [txt_max_width, txt_max_height],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=15,
        visible=is_dimension_initial,
    )
    txt_percentage = ft.TextField(
        label=t("lbl_scale_percentage"),
        value=str(saved_opts.get("percentage", "50")),
        width=385,
        filled=True,
        bgcolor=get_color("card_bg"),
        fill_color=get_color("card_bg"),
        focused_bgcolor=get_color("card_hover"),
        border_color=ft.Colors.with_opacity(0.45, get_color("primary")),
        border_width=1,
        focused_border_color=get_color("primary"),
        focused_border_width=1.5,
        suffix="%",
        keyboard_type=ft.KeyboardType.NUMBER,
        visible=not is_dimension_initial,
    )

    def on_mode_change(_: Any) -> None:
        is_dimension = (dd_mode.value or "dimension") == "dimension"
        dimension_row.visible = is_dimension
        txt_percentage.visible = not is_dimension
        page.update()

    dd_mode.on_select = on_mode_change

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
        selected_paths=selected_paths,
        route_key=ROUTE_KEY,
        get_state=lambda: {
            "mode": dd_mode.value or "dimension",
            "max_width": txt_max_width.value or "",
            "max_height": txt_max_height.value or "",
            "percentage": txt_percentage.value or "",
        },
    )
