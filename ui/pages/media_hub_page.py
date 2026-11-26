from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import flet as ft

from ui.components.nav_row_card import build_nav_row_card
from ui.components.neon_brand_text import build_neon_brand_title
from ui.i18n import t
from ui.theme import get_color


def _resolve_option_str(option: Any, key: str) -> str:
    """Extracts a string attribute or dictionary field from a hub option entry."""
    if isinstance(option, dict):
        return str(option.get(key, ""))
    return str(getattr(option, key, ""))


def _resolve_option_icon(option: Any) -> ft.IconData:
    """Extracts the icon field preserving ft.IconData instances."""
    if isinstance(option, dict):
        return option.get("icon", ft.Icons.CIRCLE)
    return getattr(option, "icon", ft.Icons.CIRCLE)


def create_media_hub_page(
    page: ft.Page,
    selected_paths: dict[str, Path],
    on_navigate: Callable[[str], None],
    main_icon: ft.IconData,
    heading_key: str,
    subheading_key: str,
    options: Sequence[Any],
) -> ft.Container:
    """Generic polymorphic hub page builder for media modules (Images, Videos, Audio)."""
    return ft.Container(
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.symmetric(horizontal=24, vertical=20),
        content=ft.Column(
            controls=list[ft.Control]([
                build_neon_brand_title(
                    value=t(heading_key),
                    size=28,
                    letter_spacing=0.8,
                ),
                ft.Text(
                    t(subheading_key),
                    size=13,
                    color=get_color("subtext"),
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=16),
                ft.Column(
                    controls=list[ft.Control]([
                        build_nav_row_card(
                            title_key=_resolve_option_str(opt, "title_key"),
                            description_key=_resolve_option_str(opt, "desc_key"),
                            icon=_resolve_option_icon(opt),
                            route_key=_resolve_option_str(opt, "route_key"),
                            on_navigate=on_navigate,
                        )
                        for opt in options
                    ]),
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                ),
            ]),
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
        ),
    )
