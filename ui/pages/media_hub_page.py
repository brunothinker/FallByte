from pathlib import Path
from typing import Any, Callable, Dict, List
import flet as ft

from ui.i18n import t
from ui.theme import (
    COLOR_CARD_BG,
    COLOR_CARD_HOVER,
    COLOR_ICON,
    COLOR_PRIMARY,
    COLOR_SUBTEXT,
    COLOR_TEXT,
)


def create_media_hub_page(
    page: ft.Page,
    selected_paths: Dict[str, Path],
    on_navigate: Callable[[str], None],
    main_icon: str,
    heading_key: str,
    subheading_key: str,
    options: List[Dict[str, Any]],
) -> ft.Container:
    """
    Generic polymorphic hub page builder for media modules (Images, Videos, etc.).

    Args:
        page (ft.Page): Current Flet window page instance.
        selected_paths (Dict[str, Path]): Context dictionary holding shared global paths.
        on_navigate (Callable[[str], None]): Navigation callback function for route transitions.
        main_icon (str): Top header Flet icon identifier string.
        heading_key (str): i18n translation key for main module heading.
        subheading_key (str): i18n translation key for module subtitle.
        options (List[Dict[str, Any]]): List of option dictionary configurations for tool cards.

    Returns:
        ft.Container: Centered container layout housing tool selection cards.
    """

    def build_option_card(
        title_key: str,
        description_key: str,
        icon: str,
        route_key: str,
    ) -> ft.Container:
        """Constructs a clickable option selection card for media operations."""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(icon, size=40, color=COLOR_PRIMARY),
                    ft.Text(
                        t(title_key),
                        size=18,
                        weight="bold",
                        color=COLOR_TEXT,
                    ),
                    ft.Text(
                        t(description_key),
                        size=12,
                        color=COLOR_SUBTEXT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=260,
            height=190,
            padding=20,
            bgcolor=COLOR_CARD_BG,
            border_radius=12,
            ink=True,
            on_click=lambda _: on_navigate(route_key),
            on_hover=lambda e: setattr(
                e.control,
                "bgcolor",
                COLOR_CARD_HOVER if e.data == "true" else COLOR_CARD_BG,
            )
            or e.control.update(),
        )

    # Return fully centered container expanding across available screen space
    return ft.Container(
        expand=True,
        alignment=ft.alignment.center,
        padding=25,
        content=ft.Column(
            [
                ft.Icon(main_icon, size=50, color=COLOR_ICON),
                ft.Text(
                    t(heading_key),
                    size=26,
                    weight="bold",
                    color=COLOR_TEXT,
                ),
                ft.Text(t(subheading_key), color=COLOR_SUBTEXT),
                ft.Container(height=20),
                ft.Row(
                    [
                        build_option_card(
                            title_key=opt["title_key"],
                            description_key=opt["desc_key"],
                            icon=opt["icon"],
                            route_key=opt["route_key"],
                        )
                        for opt in options
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