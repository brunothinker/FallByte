"""Theme management module providing dynamic palette lookup and active preset configurations."""

import inspect

import flet as ft

# Color palette presets divided between Dark and Light mode variations
THEME_PRESETS: dict[str, dict[str, str]] = {
    # --- DARK THEMES ---
    "blue_dark": {
        "primary": ft.colors.BLUE_600,
        "icon": ft.colors.BLUE_400,
        "background": "#12141C",
        "sidebar_bg": "#181B26",
        "card_bg": "#1E222D",
        "card_hover": "#2A2F3D",
        "text": "#FFFFFF",
        "subtext": "#8C93A8",
    },
    "purple_dark": {
        "primary": ft.colors.PURPLE_600,
        "icon": ft.colors.PURPLE_300,
        "background": "#120E1A",
        "sidebar_bg": "#171221",
        "card_bg": "#1D162B",
        "card_hover": "#2B213D",
        "text": "#FFFFFF",
        "subtext": "#9B8EB3",
    },
    "emerald_dark": {
        "primary": ft.colors.TEAL_600,
        "icon": ft.colors.TEAL_400,
        "background": "#0D1815",
        "sidebar_bg": "#111F1C",
        "card_bg": "#152622",
        "card_hover": "#203832",
        "text": "#FFFFFF",
        "subtext": "#85A39B",
    },
    "red_dark": {
        "primary": ft.colors.RED_600,
        "icon": ft.colors.RED_400,
        "background": "#1A0E0E",
        "sidebar_bg": "#221212",
        "card_bg": "#2B1616",
        "card_hover": "#3D2121",
        "text": "#FFFFFF",
        "subtext": "#B38E8E",
    },
    "amber_dark": {
        "primary": ft.colors.AMBER_600,
        "icon": ft.colors.AMBER_400,
        "background": "#1A160E",
        "sidebar_bg": "#221D12",
        "card_bg": "#2B2416",
        "card_hover": "#3D3321",
        "text": "#FFFFFF",
        "subtext": "#B3A48E",
    },
    # --- LIGHT THEMES (Vibrant sidebar and high contrast background) ---
    "blue_light": {
        "primary": ft.colors.BLUE_700,
        "icon": ft.colors.BLUE_700,
        "background": "#EBF2FA",  # Crisp pastel ice-blue background
        "sidebar_bg": "#D0E1F9",  # Accentuated blue navigation sidebar
        "card_bg": "#FFFFFF",     # Pure white elevated card background
        "card_hover": "#C0D7F7",
        "text": "#0F172A",
        "subtext": "#334155",
    },
    "purple_light": {
        "primary": ft.colors.PURPLE_700,
        "icon": ft.colors.PURPLE_700,
        "background": "#F4EBFB",  # Pastel light lilac background
        "sidebar_bg": "#E2CBF7",  # Distinct purple navigation sidebar
        "card_bg": "#FFFFFF",
        "card_hover": "#D5B5F3",
        "text": "#1E152A",
        "subtext": "#4C3860",
    },
    "emerald_light": {
        "primary": ft.colors.TEAL_800,
        "icon": ft.colors.TEAL_800,
        "background": "#E6F4F1",  # Pastel teal background
        "sidebar_bg": "#BCE3DA",  # Prominent emerald/teal sidebar
        "card_bg": "#FFFFFF",
        "card_hover": "#A2D5C8",
        "text": "#0D1F1A",
        "subtext": "#2D4A43",
    },
    "red_light": {
        "primary": ft.colors.RED_700,
        "icon": ft.colors.RED_700,
        "background": "#FCEAEA",  # Light coral/rose background
        "sidebar_bg": "#F7C5C5",  # Highly noticeable red/crimson sidebar
        "card_bg": "#FFFFFF",
        "card_hover": "#F2A8A8",
        "text": "#241010",
        "subtext": "#543030",
    },
    "amber_light": {
        "primary": ft.colors.AMBER_900,
        "icon": ft.colors.AMBER_900,
        "background": "#FAF0DC",  # Warm beige background
        "sidebar_bg": "#F3D8A5",  # Strong golden/amber sidebar
        "card_bg": "#FFFFFF",
        "card_hover": "#EBC580",
        "text": "#211A0E",
        "subtext": "#4A3B22",
    },
}

# Global active theme key identifier
CURRENT_THEME_KEY: str = "blue_dark"

# Standard layout dimensional constants across form pages
FORM_WIDTH = 550
BUTTON_HEIGHT = 45

# Font stack shared by the Flet theme
FONT_FAMILY = "system-ui, -apple-system, BlinkMacSystemFont, sans-serif"


def set_active_theme(theme_key: str) -> None:
    """Sets active theme preset key globally across application context.

    Args:
        theme_key (str): Target theme identifier key present in THEME_PRESETS.
    """
    global CURRENT_THEME_KEY
    if theme_key in THEME_PRESETS:
        CURRENT_THEME_KEY = theme_key
    else:
        CURRENT_THEME_KEY = "blue_dark"


def get_color(color_key: str) -> str:
    """Dynamically retrieves color hexadecimal value associated with current active theme.

    Args:
        color_key (str): Requested color property key name.

    Returns:
        str: Hexadecimal color string or default fallback value.
    """
    preset = THEME_PRESETS.get(CURRENT_THEME_KEY, THEME_PRESETS["blue_dark"])
    if color_key in preset:
        return preset[color_key]

    # Static invariant status color mappings
    static_colors = {
        "success": ft.colors.GREEN_600,
        "error": ft.colors.RED_600,
        "warning": ft.colors.AMBER_600,
    }
    return static_colors.get(color_key, "#FFFFFF")


def build_flet_theme() -> ft.Theme:
    """Builds a Flet Theme whose color scheme follows the active preset.

    Controls that Flet paints on its own (popup menus, dropdown menus, sliders,
    text fields, dialogs) read their colors from this scheme, so without it
    they fall back to the default Material blue instead of the app theme.
    """
    wanted = {
        "primary": get_color("primary"),
        "on_primary": "#FFFFFF",
        "secondary": get_color("primary"),
        "surface": get_color("card_bg"),
        "on_surface": get_color("text"),
        "surface_container": get_color("card_bg"),
        "surface_container_high": get_color("card_hover"),
        "surface_variant": get_color("card_hover"),
        "on_surface_variant": get_color("subtext"),
        "background": get_color("background"),
        "on_background": get_color("text"),
    }

    # Keep only the ColorScheme fields supported by the installed Flet version.
    valid_fields = inspect.signature(ft.ColorScheme).parameters
    scheme = ft.ColorScheme(
        **{key: value for key, value in wanted.items() if key in valid_fields}
    )

    return ft.Theme(
        font_family=FONT_FAMILY,
        use_material3=True,
        color_scheme=scheme,
    )