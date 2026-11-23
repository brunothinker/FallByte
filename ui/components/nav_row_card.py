"""Shared horizontal navigation card used by the Home dashboard and the media hubs."""

from collections.abc import Callable

import flet as ft

from ui.i18n import t
from ui.theme import get_color

NAV_ROW_CARD_WIDTH = 580


def build_nav_row_card(
    title_key: str,
    description_key: str,
    icon: str,
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

    def on_hover(e: ft.ControlEvent) -> None:
        is_hovered = e.data == "true"
        e.control.bgcolor = (
            get_color("card_hover") if is_hovered else get_color("card_bg")
        )
        e.control.border = ft.border.all(
            1,
            get_color("primary") if is_hovered else ft.colors.OUTLINE_VARIANT,
        )
        e.control.update()

    return ft.Container(
        width=width,
        padding=ft.padding.symmetric(horizontal=20, vertical=15),
        bgcolor=get_color("card_bg"),
        border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
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
                    bgcolor=ft.colors.with_opacity(0.12, get_color("primary")),
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
                    ft.icons.CHEVRON_RIGHT,
                    size=20,
                    color=get_color("subtext"),
                ),
            ],
            spacing=16,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )
