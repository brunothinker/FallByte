from collections.abc import Callable
from typing import Any

import flet as ft

from ui.components.io_picker_card import CARD_HEIGHT, CARD_WIDTH
from ui.i18n import t
from ui.theme import get_color


def create_source_picker_card(
    lbl_in_path: ft.Text,
    on_select_file: Callable[[], None],
    on_select_folder: Callable[[], None],
    file_icon: ft.IconData = ft.Icons.UPLOAD_FILE,
) -> ft.Container:
    """Constructs a source selection card matching the destination card with hover-revealed actions."""
    default_view = ft.Column(
        [
            ft.Icon(ft.Icons.FOLDER_OPEN, size=28, color=get_color("primary")),
            ft.Text(
                t("lbl_source"),
                size=12,
                weight=ft.FontWeight.W_600,
                color=get_color("text"),
                text_align=ft.TextAlign.CENTER,
            ),
            lbl_in_path,
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=4,
    )

    def _build_option_row(
        icon: ft.IconData, label: str, callback: Callable[[], None]
    ) -> ft.Container:
        def on_opt_hover(e: Any) -> None:
            hovered = e.data in (True, "true")
            e.control.bgcolor = (
                get_color("card_hover") if hovered else ft.Colors.TRANSPARENT
            )
            e.control.update()

        return ft.Container(
            expand=True,
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            border_radius=8,
            ink=True,
            on_hover=on_opt_hover,
            on_click=lambda _: callback(),
            content=ft.Row(
                [
                    ft.Icon(icon, size=18, color=get_color("primary")),
                    ft.Text(
                        label,
                        size=12,
                        weight=ft.FontWeight.W_500,
                        color=get_color("text"),
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
        )

    hover_view = ft.Column(
        [
            _build_option_row(file_icon, t("lbl_select_file"), on_select_file),
            ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
            _build_option_row(ft.Icons.FOLDER, t("lbl_select_folder"), on_select_folder),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        spacing=4,
        visible=False,
    )

    def _set_card_active(card: ft.Container, active: bool) -> None:
        primary = get_color("primary")
        card.border = ft.Border.all(
            1.5 if active else 1,
            primary if active else ft.Colors.with_opacity(0.45, primary),
        )
        card.shadow = (
            ft.BoxShadow(
                blur_radius=14,
                spread_radius=1,
                color=ft.Colors.with_opacity(0.45, primary),
                blur_style=ft.BlurStyle.NORMAL,
            )
            if active
            else None
        )
        default_view.visible = not active
        hover_view.visible = active
        card.update()

    def on_card_hover(e: Any) -> None:
        _set_card_active(e.control, e.data in (True, "true"))

    def on_card_click(e: Any) -> None:
        if default_view.visible:
            _set_card_active(e.control, True)

    return ft.Container(
        width=CARD_WIDTH,
        height=CARD_HEIGHT,
        bgcolor=get_color("card_bg"),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.45, get_color("primary"))),
        border_radius=12,
        padding=10,
        on_hover=on_card_hover,
        on_click=on_card_click,
        content=ft.Stack(
            [
                ft.Container(content=default_view, alignment=ft.Alignment.CENTER),
                ft.Container(content=hover_view, alignment=ft.Alignment.CENTER),
            ]
        ),
    )
