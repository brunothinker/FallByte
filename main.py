import argparse
import atexit
import logging
import os
import subprocess
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import flet as ft

from src.audio.utils import audio_ffmpeg_utils
from src.utils.config_manager import CONFIG_DIR, load_config
from src.utils.smoke_check import run_smoke_check
from src.video.utils import video_ffmpeg_utils
from ui.app_layout import create_app_layout
from ui.i18n import AVAILABLE_LANGUAGES, detect_system_language, set_language, t
from ui.theme import build_flet_theme, get_color, set_active_theme

APP_VERSION = "dev"

# Setup module logger
logger = logging.getLogger(__name__)

# Log file living next to the user configuration
LOG_FILE = CONFIG_DIR / "fallbyte.log"

# Window geometry
WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 720
WINDOW_MIN_WIDTH = 800
WINDOW_MIN_HEIGHT = 600


def shutdown_active_processes() -> None:
    """Terminates any running video or audio FFmpeg subprocesses on exit."""
    for termination_fn in (
        video_ffmpeg_utils.terminate_active_processes,
        audio_ffmpeg_utils.terminate_active_processes,
    ):
        try:
            termination_fn()
        except (OSError, subprocess.SubprocessError) as err:
            logger.debug("Error while terminating active FFmpeg processes: %s", err)


def parse_cli_args() -> argparse.Namespace:
    """Parses command-line arguments passed before UI startup.

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

    if any((handler.name or "").startswith("fallbyte_") for handler in root.handlers):
        return LOG_FILE

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.name = "fallbyte_file"
    root.addHandler(file_handler)

    if sys.stderr is not None:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        stream_handler.name = "fallbyte_stream"
        root.addHandler(stream_handler)

    return LOG_FILE


def configure_window(page: ft.Page) -> None:
    """Applies window size/minimum size and registers the close handler.

    Args:
        page (ft.Page): Root Flet page window instance.
    """
    def _on_window_event(e: ft.ControlEvent) -> None:
        if e.data == "close":
            shutdown_active_processes()

    page.on_window_event = _on_window_event

    def _apply_geometry() -> None:
        page.window_width = WINDOW_WIDTH
        page.window_height = WINDOW_HEIGHT
        page.window_min_width = WINDOW_MIN_WIDTH
        page.window_min_height = WINDOW_MIN_HEIGHT
        page.update()

    try:
        # Set size, position and resizability in ONE update while the window
        # is still hidden, so the window manager sees a single, consistent
        # geometry change instead of several racing ones.
        page.window_resizable = True
        _apply_geometry()
        page.window_center()
        page.update()
    except Exception as err:  # noqa: BLE001 - geometry is best-effort only
        logger.debug("Could not apply window geometry: %s", err)
    finally:
        # The window starts hidden (see FLET_HIDE_WINDOW_ON_START below);
        # always make it visible, even if applying the geometry failed.
        page.window_visible = True
        page.update()


def main(page: ft.Page) -> None:
    """Initializes configuration, themes, i18n, and root UI layout.

    Args:
        page (ft.Page): Root Flet page window instance.
    """
    user_config = load_config()
    saved_lang = user_config.get("language")
    saved_theme = user_config.get("theme", "blue_dark")

    # Configure active language setting: use saved choice or detect locale
    if saved_lang in AVAILABLE_LANGUAGES:
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

    # Flet-drawn controls follow the active preset across light and dark modes
    page.theme = build_flet_theme()
    page.dark_theme = build_flet_theme()

    # Standard desktop window dimensions with window controls preserved
    configure_window(page)

    page.on_disconnect = lambda _: shutdown_active_processes()

    # Context dictionary holding global file paths across views
    selected_paths: dict[str, Path] = {}

    # Assemble and mount primary layout frame to root page
    page.add(create_app_layout(page, selected_paths, app_version=APP_VERSION))
    page.update()


def prefer_x11_on_wayland() -> None:
    """Forces the GTK client to run through XWayland on Wayland sessions.

    Wayland compositors (GNOME/Mutter on Ubuntu) ignore client-requested
    window sizes and positions. Running the Flet desktop client under X11
    (XWayland) can make them work, but it may also break the maximized
    state. Opt-in only: set ``FALLBYTE_FORCE_X11=1`` to enable it.
    """
    if not sys.platform.startswith("linux"):
        return
    if os.environ.get("FALLBYTE_FORCE_X11") != "1":
        return
    if os.environ.get("XDG_SESSION_TYPE") == "wayland" and os.environ.get("DISPLAY"):
        os.environ.setdefault("GDK_BACKEND", "x11")


if __name__ == "__main__":
    atexit.register(shutdown_active_processes)
    args = parse_cli_args()
    log_path = setup_logging(debug=args.debug)
    logger.info("FallByte %s starting; log file: %s", APP_VERSION, log_path)

    if args.smoke_test:
        success = run_smoke_check()
        sys.exit(0 if success else 1)

    prefer_x11_on_wayland()
    # Start the desktop window hidden; configure_window() shows it once the
    # size is applied, which avoids the random "default size" window.
    os.environ.setdefault("FLET_HIDE_WINDOW_ON_START", "true")
    ft.app(target=main)
