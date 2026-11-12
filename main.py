import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


import flet as ft


from src.utils.config_manager import CONFIG_DIR, load_config
from src.utils.smoke_check import run_smoke_check
from ui.app_layout import create_app_layout
from ui.i18n import TRANSLATIONS, detect_system_language, set_language, t
from ui.theme import build_flet_theme, get_color, set_active_theme

APP_VERSION = "dev"

# Setup module logger
logger = logging.getLogger(__name__)

# Log file living next to the user configuration
LOG_FILE = CONFIG_DIR / "fallbyte.log"


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
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging (default level is INFO).",
    )
    return parser.parse_args()


def setup_logging(debug: bool = False) -> Path:
    """Configures root logging once at startup.

    Adds a rotating file handler (1 MB, 3 backups) writing to ``LOG_FILE``
    in the configuration directory, plus a console handler when stderr is
    available (desktop/exe launches may not have one). Calling it again
    does not duplicate handlers; only the level is updated.

    Args:
        debug: When True the root level is DEBUG, otherwise INFO.

    Returns:
        Path: The log file path.
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    if any(getattr(handler, "_fallbyte_handler", False) for handler in root.handlers):
        return LOG_FILE

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler._fallbyte_handler = True
    root.addHandler(file_handler)

    if sys.stderr is not None:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        stream_handler._fallbyte_handler = True
        root.addHandler(stream_handler)

    return LOG_FILE


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
        ft.ThemeMode.DARK if user_config.get("theme_mode", "dark") == "dark" else ft.ThemeMode.LIGHT
    )
    page.theme = build_flet_theme(get_color(saved_theme))
    page.window_width = 1280
    page.window_height = 800
    page.window_min_width = 1000
    page.window_min_height = 700
    page.padding = 0
    page.spacing = 0

    create_app_layout(page)

    page.update()


if __name__ == "__main__":
    args = parse_cli_args()
    log_path = setup_logging(debug=args.debug)
    logger.info(f"FallByte {APP_VERSION} starting; log file: {log_path}")
    if args.smoke_test:
        raise SystemExit(run_smoke_check())
    ft.app(
        target=main,
        view=ft.AppView.FLET_APP,
    )
