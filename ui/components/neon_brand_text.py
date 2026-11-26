import flet as ft

from ui.theme import get_color


def build_neon_brand_title(
    value: str,
    size: float,
    glow_intensity: float = 0.28,
) -> ft.Container:
    """Renders brand text with a soft primary shadow without a solid pill background."""
    primary = get_color("primary")

    char_factor = 0.64 if size >= 30 else 0.60
    box_width = max(120.0, len(value) * size * char_factor)

    # The text line is taller than the font size (Segoe UI is ~1.33x), so the
    # box needs enough vertical room or descenders ("y", "g", "p") get clipped.
    box_height = size * 1.6

    # Keep the glow the same size as before the box was made taller.
    glow_base_height = size * 1.25

    glow_halo = ft.Container(
        width=box_width * 0.85,
        height=glow_base_height * 0.65,
        border_radius=glow_base_height,
        shadow=[
            ft.BoxShadow(
                spread_radius=0,
                blur_radius=size * 0.95,
                color=ft.Colors.with_opacity(glow_intensity, primary),
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
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Container(
                    width=box_width,
                    height=box_height,
                    content=label,
                    alignment=ft.Alignment.CENTER,
                ),
            ],
        ),
        alignment=ft.Alignment.CENTER,
    )
