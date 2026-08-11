from typing import Callable
import flet as ft

from ui.theme import COLOR_CARD_BG, COLOR_PRIMARY, COLOR_TEXT


def create_clickable_card(
    title: str, icon: str, lbl_text: ft.Text, on_click_action: Callable
) -> ft.Container:
    """
    Constructs a responsive card container for direct file or directory selection.

    Args:
        title (str): Card title text displayed below icon.
        icon (str): Flet icon name identifier.
        lbl_text (ft.Text): UI text component rendering selection path status.
        on_click_action (Callable): Callback triggered when card is clicked.

    Returns:
        ft.Container: Configured clickable selection card UI component.
    """
    return ft.Container(
        width=185,
        height=125,
        bgcolor=COLOR_CARD_BG,
        border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
        border_radius=12,
        padding=10,
        ink=True,
        on_click=on_click_action,
        content=ft.Column(
            [
                ft.Icon(icon, size=28, color=COLOR_PRIMARY),
                ft.Text(
                    title,
                    size=12,
                    weight=ft.FontWeight.W_600,
                    color=COLOR_TEXT,
                    text_align=ft.TextAlign.CENTER,
                ),
                lbl_text,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        ),
    )