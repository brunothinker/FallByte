import logging
from pathlib import Path
from typing import Callable, Dict, Any
import flet as ft

from ui.i18n import t
from ui.pages.home_page import create_home_page
from ui.pages.image.image_hub_page import create_image_hub_page

# Setup module logger
logger = logging.getLogger(__name__)

# Fallback imports for Image Hubs supporting flat and nested directory structures
try:
    from ui.pages.image.conversion_hub_page import create_conversion_hub_page
    from ui.pages.image.compression_hub_page import create_compression_hub_page
except ImportError:
    from ui.pages.image.conversion.conversion_hub_page import create_conversion_hub_page
    from ui.pages.image.compression.compression_hub_page import create_compression_hub_page

# Fallback imports for Image Conversion pages
try:
    from ui.pages.image.conversion_pages import (
        create_conversion_file_page,
        create_conversion_dir_page,
    )
except ImportError:
    from ui.pages.image.conversion.conversion_pages import (
        create_conversion_file_page,
        create_conversion_dir_page,
    )

# Fallback imports for Image Compression pages
try:
    from ui.pages.image.compression_pages import (
        create_compression_file_page,
        create_compression_dir_page,
    )
except ImportError:
    from ui.pages.image.compression.compression_pages import (
        create_compression_file_page,
        create_compression_dir_page,
    )

# Centralized router registry mapping application routes to title keys and view builders
ROUTE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "home": {
        "title_key": "home_header_title",
        "builder": create_home_page,
    },
    "image_hub": {
        "title_key": "image_hub_header_title",
        "builder": create_image_hub_page,
    },
    "conversion_hub": {
        "title_key": "conversion_hub_header_title",
        "builder": create_conversion_hub_page,
    },
    "compression_hub": {
        "title_key": "compression_hub_header_title",
        "builder": create_compression_hub_page,
    },
    "image_conversion_file": {
        "title_key": "form_conversion_file_title",
        "builder": create_conversion_file_page,
    },
    "image_conversion_dir": {
        "title_key": "form_conversion_dir_title",
        "builder": create_conversion_dir_page,
    },
    "image_compression_file": {
        "title_key": "form_compression_file_title",
        "builder": create_compression_file_page,
    },
    "image_compression_dir": {
        "title_key": "form_compression_dir_title",
        "builder": create_compression_dir_page,
    },
}


def build_page_view(
    route_key: str,
    page: ft.Page,
    selected_paths: Dict[str, Path],
    on_navigate: Callable[[str], None],
) -> ft.Control:
    """
    Constructs and returns the view component corresponding to a given route key.

    Args:
        route_key (str): Unique route key string matching an entry in ROUTE_REGISTRY.
        page (ft.Page): Current Flet window page instance.
        selected_paths (Dict[str, Path]): Context dictionary holding shared global paths.
        on_navigate (Callable[[str], None]): Navigation callback function for routing transitions.

    Returns:
        ft.Control: Constructed layout container for the route or an error text component.
    """
    route_info = ROUTE_REGISTRY.get(route_key)
    if route_info and "builder" in route_info:
        return route_info["builder"](page, selected_paths, on_navigate)

    logger.warning(f"Attempted navigation to unknown route key: '{route_key}'")
    return ft.Text(t("route_not_found", route_key=route_key), color="red")