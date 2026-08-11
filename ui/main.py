import logging
from typing import Dict
from pathlib import Path
import flet as ft

# Imports targeting the clean ui architecture
from ui.app_layout import create_app_layout
from ui.i18n import t

# Setup main entrypoint logger
logger = logging.getLogger(__name__)


def main(page: ft.Page) -> None:
    """
    Main application entry point configuring window properties,
    global theme settings, and rendering the root layout.

    Args:
        page (ft.Page): Root Flet window page instance.
    """
    page.title = t("app_title")
    page.theme_mode = ft.ThemeMode.DARK

    # Smart system font detection: uses native system font stack with fallback
    page.theme = ft.Theme(
        font_family="system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
        use_material3=True
    )

    page.window_width = 520
    page.window_height = 800
    page.window_center()

    # Context dictionary holding shared global paths across views
    selected_paths: Dict[str, Path] = {}

    # Render root application frame
    page.add(create_app_layout(page, selected_paths))


if __name__ == "__main__":
    ft.app(target=main)