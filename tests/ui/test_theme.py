"""UI: theme."""

import flet as ft


def test_theme_get_color_danger_resolution():
    """Verifies get_color returns static danger color without fallback to white."""
    from ui.theme import get_color

    danger_color = get_color("danger")
    assert danger_color == ft.colors.RED_600, (
        "[ui] get_color('danger') must resolve to static ft.colors.RED_600."
    )
    assert danger_color != "#FFFFFF", (
        "[ui] get_color('danger') must not fall back to default white '#FFFFFF'."
    )
