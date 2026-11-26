
"""Shared horizontal navigation card used by the Home dashboard and the media hubs."""

from collections.abc import Callable
from typing import Any

import flet as ft

from ui.i18n import t
from ui.theme import get_color

NAV_ROW_CARD_WIDTH = 580


def build_nav_row_card(
    title_key: str,
    description_key: str,
    icon: ft.IconData,
    route_key: str,
    on_navigate: Callable[[str], None],
    width: int = NAV_ROW_CARD_WIDTH,
) -> ft.Container:
    """Constructs a horizontal list-style card that navigates to a route when clicked.

    Args:
        title_key (str): i18n key for the card title.
        description_key (str): i18n key for the card description.
        icon (str): Flet icon name shown on the leading badge.
        route_key (str): Route identifier passed to ``on_navigate``.
        on_navigate (Callable[[str], None]): Navigation callback.
        width (int, optional): Card width. Defaults to ``NAV_ROW_CARD_WIDTH``.

    Returns:
        ft.Container: Configured navigation card.
    """

    def on_hover(e: Any) -> None:
        is_hovered = e.data in (True, "true")
        primary = get_color("primary")
        e.control.bgcolor = (
            get_color("card_hover") if is_hovered else get_color("card_bg")
        )
        e.control.border = ft.Border.all(
            1.5 if is_hovered else 1,
            primary if is_hovered else ft.Colors.OUTLINE_VARIANT,
        )
        e.control.shadow = (
            ft.BoxShadow(
                blur_radius=14,
                spread_radius=1,
                color=ft.Colors.with_opacity(0.45, primary),
                blur_style=ft.BlurStyle.NORMAL,
            )
            if is_hovered
            else None
        )
        e.control.update()

    return ft.Container(
        width=width,
        padding=ft.Padding.symmetric(horizontal=20, vertical=15),
        bgcolor=get_color("card_bg"),
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        border_radius=12,
        ink=True,
        on_click=lambda _: on_navigate(route_key),
        on_hover=on_hover,
        content=ft.Row(
            controls=[
                ft.Container(
                    content=ft.Icon(icon, size=24, color=get_color("primary")),
                    padding=11,
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.12, get_color("primary")),
                ),
                ft.Column(
                    controls=[
                        ft.Text(
                            t(title_key),
                            size=15,
                            weight=ft.FontWeight.W_600,
                            color=get_color("text"),
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            t(description_key),
                            size=12,
                            color=get_color("subtext"),
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    spacing=3,
                    expand=True,
                ),
                ft.Icon(
                    ft.Icons.CHEVRON_RIGHT,
                    size=20,
                    color=get_color("subtext"),
                ),
            ],
            spacing=16,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )
