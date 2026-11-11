import argparse
import logging
import sys
from pathlib import Path

import flet as ft

from src.utils.config_manager import load_config
from src.utils.smoke_check import run_smoke_check
from ui.app_layout import create_app_layout
from ui.i18n import TRANSLATIONS, detect_system_language, set_language, t
from ui.theme import build_flet_theme, get_color, set_active_theme

APP_VERSION = "dev"

# Setup module logger
logger = logging.getLogger(__name__)


def parse_cli_args() -> argparse.Namespace:
    """Parses command-line arguments passed to FallByte executable before UI startup.

    Returns:
        argparse.Namespace: Object containing evaluated CLI flags.
    """
    parser = argparse.ArgumentParser(
        description="FallByte - Local-first media optimization suite.",
        add_help=True,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"FallByte {APP_VERSION}",
        help="Show application version and exit.",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Execute automated runtime dependency and binary sanity checks.",
    )
    return parser.parse_args()


def main(page: ft.Page) -> None:
    """Main application entry point initializing configuration, themes, i18n, and root UI.

    Args:
        page (ft.Page): Root Flet page window instance.
    """
    user_config = load_config()
    saved_lang = user_config.get("language")
    saved_theme = user_config.get("theme", "blue_dark")

    # Configure active language setting: use saved choice or detect system locale
    if saved_lang in TRANSLATIONS:
        set_language(saved_lang)
    else:
        set_language(detect_system_language())

    # Apply saved theme configuration from persistent storage
    set_active_theme(saved_theme)

    page.title = t("app_title")
    page.theme_mode = (
        ft.ThemeMode.LIGHT if saved_theme.endswith("_light") else ft.ThemeMode.DARK
    )

    # Set native page background color to match active theme
    page.bgcolor = get_color("background")

    # Flet-drawn controls (popup menus, dropdowns, sliders...) follow the
    # active preset. Both themes are set because the mode switches between
    # LIGHT and DARK depending on the selected preset.
    page.theme = build_flet_theme()
    page.dark_theme = build_flet_theme()

    # Configure standard desktop application window dimensions
    page.window_width = 1100
    page.window_height = 720
    page.window_min_width = 900
    page.window_min_height = 600
    page.window_center()

    # Context dictionary holding global file paths across views
    selected_paths: dict[str, Path] = {}

    # Assemble and mount primary layout frame to root page
    page.add(create_app_layout(page, selected_paths, app_version=APP_VERSION))


if __name__ == "__main__":
    args = parse_cli_args()

    if args.smoke_test:
        success = run_smoke_check()
        sys.exit(0 if success else 1)

    ft.app(target=main)