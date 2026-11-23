from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import flet as ft

from ui.i18n import t
from ui.theme import get_color


def _resolve_option_field(option: Any, key: str) -> str:
    """Extracts a string attribute or dictionary field from a hub option entry."""
    if isinstance(option, dict):
        return str(option.get(key, ""))
    return str(getattr(option, key, ""))


def create_media_hub_page(
    page: ft.Page,
    selected_paths: dict[str, Path],
    on_navigate: Callable[[str], None],
    main_icon: str,
    heading_key: str,
    subheading_key: str,
    options: Sequence[Any],
) -> ft.Container:
    """Generic polymorphic hub page builder for media modules (Images, Videos, Audio)."""

    def build_option_row_card(
        title_key: str,
        description_key: str,
        icon: str,
        route_key: str,
    ) -> ft.Container:
        """Constructs a horizontal list-style card matching the Home layout."""

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
            width=580,
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

    return ft.Container(
        alignment=ft.alignment.center,
        padding=ft.padding.symmetric(horizontal=24, vertical=20),
        content=ft.Column(
            controls=[
                ft.Text(
                    t(heading_key),
                    size=26,
                    weight=ft.FontWeight.BOLD,
                    color=get_color("text"),
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    t(subheading_key),
                    size=13,
                    color=get_color("subtext"),
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=16),
                ft.Column(
                    controls=[
                        build_option_row_card(
                            title_key=_resolve_option_field(opt, "title_key"),
                            description_key=_resolve_option_field(opt, "desc_key"),
                            icon=_resolve_option_field(opt, "icon"),
                            route_key=_resolve_option_field(opt, "route_key"),
                        )
                        for opt in options
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
        ),
    )
