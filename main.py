import argparse
import asyncio
import atexit
import ctypes
import inspect
import logging
import os
import subprocess
import sys
import threading
import time
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

# Window/taskbar icon (relative to the project root or the PyInstaller bundle)
ICON_RELATIVE_PATH = Path("resources") / "icons" / "fallbyte_icon.ico"


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
    """Configures root logging once at startup."""
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


def resolve_icon_path() -> Path:
    """Locates the .ico file both in dev mode and inside a PyInstaller bundle."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / ICON_RELATIVE_PATH


def apply_window_icon(title: str) -> None:
    """Sets the title-bar/taskbar icon of the Flet client window (Windows only)."""
    if sys.platform != "win32":
        return

    icon_path = resolve_icon_path()
    if not icon_path.exists():
        logger.warning("Window icon not found: %s", icon_path)
        return

    def _worker() -> None:
        try:
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
            user32.FindWindowW.restype = wintypes.HWND
            user32.GetSystemMetrics.argtypes = [ctypes.c_int]
            user32.GetSystemMetrics.restype = ctypes.c_int
            user32.LoadImageW.argtypes = [
                wintypes.HINSTANCE,
                wintypes.LPCWSTR,
                wintypes.UINT,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.UINT,
            ]
            user32.LoadImageW.restype = wintypes.HANDLE
            user32.SendMessageW.argtypes = [
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            ]
            user32.SendMessageW.restype = wintypes.LPARAM

            hwnd = None
            for _ in range(100):  # up to ~20 s waiting for the client window
                hwnd = user32.FindWindowW(None, title)
                if hwnd:
                    break
                time.sleep(0.2)
            if not hwnd:
                logger.debug("Flet window not found; icon not applied.")
                return

            image_icon, lr_loadfromfile, wm_seticon = 1, 0x0010, 0x0080
            sm_cxicon, sm_cxsmicon = 11, 49
            icon_big, icon_small = 1, 0

            for kind, metric in ((icon_big, sm_cxicon), (icon_small, sm_cxsmicon)):
                size = user32.GetSystemMetrics(metric)
                handle = user32.LoadImageW(
                    None, str(icon_path), image_icon, size, size, lr_loadfromfile
                )
                if handle:
                    user32.SendMessageW(hwnd, wm_seticon, kind, handle)
        except Exception as err:  # noqa: BLE001 - icon is cosmetic only
            logger.debug("Could not apply window icon: %s", err)

    threading.Thread(target=_worker, name="fallbyte_icon", daemon=True).start()


def configure_window(page: ft.Page) -> None:
    """Applies window size/minimum size and registers the close handler."""

    async def _destroy_window() -> None:
        shutdown_active_processes()
        destroy_fn = getattr(page.window, "destroy", None)
        if callable(destroy_fn):
            try:
                res = destroy_fn()
                if inspect.isawaitable(res):
                    await res
            except RuntimeError:
                pass
        else:
            try:
                page.window.prevent_close = False
                page.update()
            except RuntimeError:
                pass

    async def _cancel_and_close_task() -> None:
        data = page.data if isinstance(getattr(page, "data", None), dict) else {}
        controller = data.get("active_controller")
        if controller is not None and hasattr(controller, "trigger_cancel"):
            controller.trigger_cancel()  # type: ignore[attr-defined]

        # Wait for the job thread to observe cancellation and run session cleanup
        # before forcing FFmpeg subprocess teardown and destroying the window.
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            is_still_running = (
                bool(getattr(controller, "is_processing", False))
                if controller is not None
                else bool((page.data or {}).get("is_processing"))
            )
            if not is_still_running:
                break
            await asyncio.sleep(0.05)

        # Fallback if a subprocess did not exit on cancel_event alone.
        shutdown_active_processes()
        await _destroy_window()

    def _show_close_confirmation(controller: object | None) -> None:
        _ = controller

        def on_keep(_: object) -> None:
            dialog.open = False
            page.pop_dialog()
            page.update()

        def on_confirm(_: object) -> None:
            dialog.open = False
            page.pop_dialog()
            page.update()
            page.run_task(_cancel_and_close_task)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(t("dialog_close_processing_title")),
            content=ft.Text(t("dialog_close_processing_body")),
            actions=[
                ft.TextButton(content=t("btn_keep_running"), on_click=on_keep),
                ft.Button(
                    content=t("btn_close_and_cancel"),
                    bgcolor=get_color("danger"),
                    color="#FFFFFF",
                    on_click=on_confirm,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dialog)

    def _on_window_event(e: ft.WindowEvent) -> None:
        if e.type != ft.WindowEventType.CLOSE:
            return
        data = page.data if isinstance(getattr(page, "data", None), dict) else {}
        if data.get("is_processing"):
            _show_close_confirmation(data.get("active_controller"))
        else:
            page.run_task(_destroy_window)

    page.window.prevent_close = True
    page.window.on_event = _on_window_event

    async def _setup_and_show() -> None:
        try:
            page.window.prevent_close = True
            page.window.resizable = True
            page.window.width = WINDOW_WIDTH
            page.window.height = WINDOW_HEIGHT
            page.window.min_width = WINDOW_MIN_WIDTH
            page.window.min_height = WINDOW_MIN_HEIGHT
            await page.window.center()
        except Exception as err:  # noqa: BLE001 - geometry is best-effort only
            logger.debug("Could not apply window geometry: %s", err)
        finally:
            page.window.visible = True
            page.update()

    page.run_task(_setup_and_show)


def main(page: ft.Page) -> None:
    """Initializes configuration, themes, i18n, and root UI layout."""
    user_config = load_config()
    saved_lang = user_config.get("language")
    saved_theme = user_config.get("theme", "blue_dark")

    if saved_lang in AVAILABLE_LANGUAGES:
        set_language(saved_lang)
    else:
        set_language(detect_system_language())

    set_active_theme(saved_theme)

    page.title = t("app_title")
    page.theme_mode = (
        ft.ThemeMode.LIGHT if saved_theme.endswith("_light") else ft.ThemeMode.DARK
    )
    page.bgcolor = get_color("background")

    page.theme = build_flet_theme()
    page.dark_theme = build_flet_theme()

    configure_window(page)
    apply_window_icon(page.title)

    page.on_disconnect = lambda _: shutdown_active_processes()

    selected_paths: dict[str, Path] = {}
    page.add(create_app_layout(page, selected_paths, app_version=APP_VERSION))
    page.update()


def prefer_x11_on_wayland() -> None:
    """Forces the GTK client to run through XWayland on Wayland sessions."""
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
    os.environ.setdefault("FLET_HIDE_WINDOW_ON_START", "true")
    ft.run(main)
