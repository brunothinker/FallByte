from collections.abc import Callable

import flet as ft

from ui.theme import get_color

# Shared dimensions for the source/destination selection cards.
CARD_WIDTH = 185
CARD_HEIGHT = 125


def create_clickable_card(
    title: str, icon: ft.IconData, lbl_text: ft.Text, on_click_action: Callable
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
        width=CARD_WIDTH,
        height=CARD_HEIGHT,
        bgcolor=get_color("card_bg"),
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        border_radius=12,
        padding=10,
        ink=True,
        on_click=on_click_action,
        content=ft.Column(
            controls=list[ft.Control]([
                ft.Icon(icon, size=28, color=get_color("primary")),
                ft.Text(
                    title,
                    size=12,
                    weight=ft.FontWeight.W_600,
                    color=get_color("text"),
                    text_align=ft.TextAlign.CENTER,
                ),
                lbl_text,
            ]),
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        ),
    )
