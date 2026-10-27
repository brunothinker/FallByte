from collections.abc import Callable
from pathlib import Path

import flet as ft

from ui.i18n import t
from ui.theme import get_color


def create_home_page(
    page: ft.Page,
    selected_paths: dict[str, Path],
    on_navigate: Callable[[str], None],
) -> ft.Container:
    """FallByte Home Page displaying main feature modules in cards."""

    def build_module_card(
        title: str, description: str, icon: str, route_key: str
    ) -> ft.Container:
        """Constructs a clickable module card component."""
        return ft.Container(
            width=220,
            height=160,
            padding=16,
            bgcolor=get_color("card_bg"),
            border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
            border_radius=12,
            ink=True,
            on_click=lambda _: on_navigate(route_key),
            on_hover=lambda e: setattr(
                e.control,
                "bgcolor",
                get_color("card_hover") if e.data == "true" else get_color("card_bg"),
            )
            or e.control.update(),
            content=ft.Column(
                [
                    ft.Icon(icon, size=36, color=get_color("primary")),
                    ft.Text(
                        title,
                        size=15,
                        weight=ft.FontWeight.W_600,
                        color=get_color("text"),
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        description,
                        size=11,
                        color=get_color("subtext"),
                        text_align=ft.TextAlign.CENTER,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        max_lines=2,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
        )

    modules = [
        {
            "title": t("home_mod_image_title"),
            "description": t("home_mod_image_desc"),
            "icon": ft.icons.IMAGE,
            "route_key": "image_hub",
        },
        {
            "title": t("home_mod_video_title"),
            "description": t("home_mod_video_desc"),
            "icon": ft.icons.VIDEO_LIBRARY,
            "route_key": "video_hub",
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
                            route_key=mod["route_key"],
                        )
                        for mod in modules
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=20,
                    wrap=True,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )