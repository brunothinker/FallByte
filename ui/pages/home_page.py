from collections.abc import Callable
from pathlib import Path

import flet as ft

from ui.components.neon_brand_text import build_neon_brand_title
from ui.i18n import t
from ui.theme import get_color


def create_home_page(
    page: ft.Page,
    selected_paths: dict[str, Path],
    on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds the main dashboard view displaying available media modules in a list."""
    from ui.registry import MODULE_REGISTRY

    def build_module_row_card(
        title_key: str,
        description_key: str,
        icon: str,
        route_key: str,
    ) -> ft.Container:
        """Constructs a horizontal list card for a top-level media module."""

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
                build_neon_brand_title(
                    value=t("home_heading"),
                    size=36,
                    letter_spacing=1.2,
                ),
                ft.Text(
                    t("home_subheading"),
                    size=13,
                    color=get_color("subtext"),
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=16),
                ft.Column(
                    controls=[
                        build_module_row_card(
                            title_key=mod.title_key,
                            description_key=mod.desc_key,
                            icon=mod.icon,
                            route_key=mod.route_key,
                        )
                        for mod in MODULE_REGISTRY
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
