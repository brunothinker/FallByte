from typing import Callable, Dict
from pathlib import Path
import flet as ft

from ui.i18n import t
from ui.theme import (
    COLOR_PRIMARY,
    COLOR_TEXT,
    COLOR_SUBTEXT,
    COLOR_CARD_BG,
    COLOR_CARD_HOVER,
)


def create_home_page(
        page: ft.Page,
        selected_paths: Dict[str, Path],
        on_navigate: Callable[[str], None]
) -> ft.Container:
    """
    FallByte Home Page displaying main feature modules in side-by-side cards.
    """

    def build_module_card(
            title: str,
            description: str,
            icon: str,
            route_key: str
    ) -> ft.Container:
        return ft.Container(
            width=220,
            height=160,
            padding=16,
            bgcolor=COLOR_CARD_BG,
            border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
            border_radius=12,
            ink=True,
            on_click=lambda _: on_navigate(route_key),
            on_hover=lambda e: setattr(
                e.control,
                "bgcolor",
                COLOR_CARD_HOVER if e.data == "true" else COLOR_CARD_BG
            ) or e.control.update(),
            content=ft.Column([
                ft.Icon(icon, size=36, color=COLOR_PRIMARY),
                ft.Text(
                    title,
                    size=15,
                    weight=ft.FontWeight.W_600,
                    color=COLOR_TEXT,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Text(
                    description,
                    size=11,
                    color=COLOR_SUBTEXT,
                    text_align=ft.TextAlign.CENTER,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    max_lines=2
                ),
            ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8
            )
        )

    modules = [
        {
            "title": t("home_mod_image_title"),
            "description": t("home_mod_image_desc"),
            "icon": ft.icons.IMAGE,
            "route_key": "image_hub"
        },
    ]

    return ft.Container(
        alignment=ft.alignment.center,
        padding=20,
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        build_module_card(
                            title=mod["title"],
                            description=mod["description"],
                            icon=mod["icon"],
                            route_key=mod["route_key"]
                        ) for mod in modules
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=20,
                    wrap=True
                )
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )
    )