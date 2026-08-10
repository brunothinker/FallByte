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


def create_conversion_hub_page(
    page: ft.Page,
    selected_paths: Dict[str, Path],
    on_navigate: Callable[[str], None]
) -> ft.Container:
    """
    Builds the Conversion Sub-Hub page for selecting single-file or directory batch format conversion.

    Args:
        page (ft.Page): Current Flet window page instance.
        selected_paths (Dict[str, Path]): Context dictionary holding shared global paths.
        on_navigate (Callable[[str], None]): Navigation callback function for route transitions.

    Returns:
        ft.Container: Centered container layout housing image conversion workflow choices.
    """

    def build_option_card(
        title: str,
        description: str,
        icon: str,
        route_key: str
    ) -> ft.Container:
        """
        Constructs an interactive selection card for image format conversion options.

        Args:
            title (str): Display title for the tool card.
            description (str): Short description of the conversion option.
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

    # Return fully centered container expanding across available window space
    return ft.Container(
        expand=True,
        alignment=ft.alignment.center,
        padding=25,
        content=ft.Column(
            [
                ft.Icon(ft.icons.TRANSFORM, size=50, color=COLOR_ICON),
                ft.Text(t("conversion_hub_heading"), size=26, weight="bold", color=COLOR_TEXT),
                ft.Text(t("conversion_hub_subheading"), color=COLOR_SUBTEXT),
                ft.Container(height=20),
                ft.Row(
                    [
                        build_option_card(
                            title=t("conversion_file_card_title"),
                            description=t("conversion_file_card_desc"),
                            icon=ft.icons.INSERT_DRIVE_FILE_OUTLINED,
                            route_key="image_conversion_file"
                        ),
                        build_option_card(
                            title=t("conversion_dir_card_title"),
                            description=t("conversion_dir_card_desc"),
                            icon=ft.icons.FOLDER_OPEN,
                            route_key="image_conversion_dir"
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=20,
                    wrap=True
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )
    )