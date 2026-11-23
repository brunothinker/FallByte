from collections.abc import Callable
from pathlib import Path

import flet as ft

from ui.components.nav_row_card import build_nav_row_card
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
                        build_nav_row_card(
                            title_key=mod.title_key,
                            description_key=mod.desc_key,
                            icon=mod.icon,
                            route_key=mod.route_key,
                            on_navigate=on_navigate,
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
