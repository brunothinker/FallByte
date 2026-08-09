from typing import Callable, Dict
from pathlib import Path
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
    Sub-Hub page for selecting between Single File or Directory (Batch) conversion.
    """

    def build_option_card(
        title: str,
        description: str,
        icon: str,
        route_key: str
    ) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Icon(icon, size=40, color=COLOR_PRIMARY),
                ft.Text(title, size=18, weight="bold", color=COLOR_TEXT),
                ft.Text(
                    description,
                    size=12,
                    color=COLOR_SUBTEXT,
                    text_align=ft.TextAlign.CENTER
                ),
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
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

    return ft.Container(
        alignment=ft.alignment.center,
        padding=25,
        content=ft.Column([
            ft.Icon(ft.icons.TRANSFORM, size=50, color=COLOR_ICON),
            ft.Text(t("conversion_hub_heading"), size=26, weight="bold", color=COLOR_TEXT),
            ft.Text(t("conversion_hub_subheading"), color=COLOR_SUBTEXT),
            ft.Container(height=20),
            ft.Row([
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
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    )