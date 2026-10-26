import logging
from pathlib import Path

import flet as ft

# Imports targeting the clean ui architecture
from src.utils.config_manager import load_config
from ui.app_layout import create_app_layout
from ui.i18n import TRANSLATIONS, set_language, t

# Setup main entrypoint logger
logger = logging.getLogger(__name__)


def main(page: ft.Page) -> None:
    """Main application entry point configuring window properties,

    global theme settings, language initialization, and rendering the root layout.

    Args:
        page (ft.Page): Root Flet window page instance.
    """
    # Load settings from local YAML configuration file
    user_config = load_config()
    saved_lang = user_config.get("language", "pt")
    saved_theme = user_config.get("theme_mode", "dark")

    if saved_lang in TRANSLATIONS:
        set_language(saved_lang)
    else:
        set_language("pt")

    page.title = t("app_title")
    page.theme_mode = (
        ft.ThemeMode.DARK if saved_theme == "dark" else ft.ThemeMode.LIGHT
    )

    # Smart system font detection: uses native system font stack with fallback
    page.theme = ft.Theme(
        font_family="system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
        use_material3=True,
    )

    # Adjusted window dimensions for desktop sidebar layout
    page.window_width = 1100
    page.window_height = 720
    page.window_min_width = 900
    page.window_min_height = 600
    page.window_center()

    # Context dictionary holding shared global paths across views
    selected_paths: dict[str, Path] = {}

    # Render root application frame
    page.add(create_app_layout(page, selected_paths))


if __name__ == "__main__":
    ft.app(target=main)