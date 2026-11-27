"""UI: theme presets, color resolution, Flet Theme builder, and neon brand title."""

import flet as ft
import pytest

from ui import theme
from ui.components.neon_brand_text import build_neon_brand_title
from ui.theme import (
    THEME_PRESETS,
    build_flet_theme,
    get_color,
    set_active_theme,
)


def test_theme_get_color_danger_resolution():
    """Verifies get_color returns static danger color without fallback to white."""
    danger_color = get_color("danger")
    assert danger_color == ft.Colors.RED_600
    assert danger_color != "#FFFFFF"


@pytest.mark.parametrize("theme_key", list(THEME_PRESETS.keys()))
def test_all_theme_presets_build_valid_flet_theme(theme_key):
    """Every registered dark/light theme preset resolves required tokens and builds ft.Theme."""
    prev = theme.CURRENT_THEME_KEY
    try:
        set_active_theme(theme_key)
        for token in (
            "background",
            "card_bg",
            "card_hover",
            "text",
            "subtext",
            "primary",
            "primary_hover",
            "border",
        ):
            val = get_color(token)
            assert isinstance(val, str) and len(val) > 0

        ft_theme = build_flet_theme()
        assert isinstance(ft_theme, ft.Theme)
        if ft_theme.color_scheme is not None:
            assert ft_theme.color_scheme.primary == get_color("primary")
    finally:
        set_active_theme(prev)


def test_build_neon_brand_title_has_proportional_height_for_descenders():
    """Neon brand inner Stack reserves height=size*1.6 so lowercase descenders are never clipped."""
    container = build_neon_brand_title("FallByte", size=30)
    assert isinstance(container, ft.Container)
    assert isinstance(container.content, ft.Stack)
    assert container.content.height == pytest.approx(48.0)
