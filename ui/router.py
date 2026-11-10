import logging
from collections.abc import Callable
from pathlib import Path

import flet as ft

from ui.i18n import t
from ui.registry import get_all_routes

# Setup module logger
logger = logging.getLogger(__name__)

# Centralized router registry derived from module definitions
ROUTE_REGISTRY = get_all_routes()


def build_page_view(
    route_key: str,
    page: ft.Page,
    selected_paths: dict[str, Path],
    on_navigate: Callable[[str], None],
) -> ft.Control:
    """Constructs and returns the view component corresponding to a given route key."""
    route_info = ROUTE_REGISTRY.get(route_key)
    if route_info and "builder" in route_info:
        return route_info["builder"](page, selected_paths, on_navigate)

    logger.warning(f"Attempted navigation to unknown route key: '{route_key}'")
    return ft.Text(t("route_not_found", route_key=route_key), color="red")