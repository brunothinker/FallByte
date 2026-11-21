import flet as ft

from ui.theme import get_color


def build_neon_brand_title(
    value: str,
    size: float,
    letter_spacing: float = 0.8,
    glow_intensity: float = 0.28,
) -> ft.Container:
    """Renders brand text with a soft primary shadow without a solid pill background."""
    del letter_spacing
    primary = get_color("primary")

    char_factor = 0.64 if size >= 30 else 0.60
    box_width = max(120.0, len(value) * size * char_factor)
    box_height = size * 1.25

    glow_halo = ft.Container(
        width=box_width * 0.85,
        height=box_height * 0.65,
        border_radius=box_height,
        shadow=[
            ft.BoxShadow(
                spread_radius=0,
                blur_radius=size * 0.95,
                color=ft.colors.with_opacity(glow_intensity, primary),
                offset=ft.Offset(0, 2),
            ),
        ],
    )

    label = ft.Text(
        value,
        size=size,
        weight=ft.FontWeight.BOLD,
        color=primary,
        text_align=ft.TextAlign.CENTER,
    )

    return ft.Container(
        content=ft.Stack(
            width=box_width,
            height=box_height,
            controls=[
                ft.Container(
                    width=box_width,
                    height=box_height,
                    content=glow_halo,
                    alignment=ft.alignment.center,
                ),
                ft.Container(
                    width=box_width,
                    height=box_height,
                    content=label,
                    alignment=ft.alignment.center,
                ),
            ],
        ),
        alignment=ft.alignment.center,
    )
