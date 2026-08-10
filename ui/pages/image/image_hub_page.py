from pathlib import Path
from typing import Callable, Dict
import flet as ft

from ui.i18n import t
from ui.theme import (
    COLOR_PRIMARY,
    COLOR_ICON,
    COLOR_TEXT,
    COLOR_SUBTEXT,
    COLOR_CARD_BG,
    COLOR_CARD_HOVER,
)


def create_image_hub_page(
    page: ft.Page,
    selected_paths: Dict[str, Path],
    on_navigate: Callable[[str], None]
) -> ft.Container:
    """
    Builds the Image Hub page rendering options for format conversion and image compression.

    Args:
        page (ft.Page): Current Flet window page instance.
        selected_paths (Dict[str, Path]): Context dictionary holding shared global paths.
        on_navigate (Callable[[str], None]): Navigation callback function for route transitions.

    Returns:
        ft.Container: Centered container layout housing image tool selection cards.
    """

    def build_option_card(
        title: str,
        description: str,
        icon: str,
        route_key: str
    ) -> ft.Container:
        """
        Constructs an option selection card for image operations.

        Args:
            title (str): Display title for the tool card.
            description (str): Short description of the utility function.
            icon (str): Flet icon identifier string.
            route_key (str): Navigation route key triggered on click.

        Returns:
            ft.Container: Configured clickable card component with hover feedback.
        """
        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(icon, size=40, color=COLOR_PRIMARY),
                    ft.Text(title, size=18, weight="bold", color=COLOR_TEXT),
                    ft.Text(
                        description,
                        size=12,
                        color=COLOR_SUBTEXT,
                        text_align=ft.TextAlign.CENTER
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
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
                COLOR_CARD_HOVER if e.data == "true" else COLOR_CARD_BG
            ) or e.control.update(),
        )

    # Return fully centered container expanding across available screen space
    return ft.Container(
        expand=True,
        alignment=ft.alignment.center,
        padding=25,
        content=ft.Column(
            [
                ft.Icon(ft.icons.IMAGE_OUTLINED, size=50, color=COLOR_ICON),
                ft.Text(t("image_hub_heading"), size=26, weight="bold", color=COLOR_TEXT),
                ft.Text(t("image_hub_subheading"), color=COLOR_SUBTEXT),
                ft.Container(height=20),
                ft.Row(
                    [
                        build_option_card(
                            title=t("image_hub_card_conversion_title"),
                            description=t("image_hub_card_conversion_desc"),
                            icon=ft.icons.TRANSFORM,
                            route_key="conversion_hub"
                        ),
                        build_option_card(
                            title=t("image_hub_card_compression_title"),
                            description=t("image_hub_card_compression_desc"),
                            icon=ft.icons.COMPRESS,
                            route_key="compression_hub"
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=20,
                    wrap=True  # Enables vertical wrapping when window is narrowed
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )
    )