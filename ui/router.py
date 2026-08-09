from pathlib import Path
from typing import Callable, Dict
import flet as ft

from ui.i18n import t
from ui.pages.home_page import create_home_page
from ui.pages.image.image_hub_page import create_image_hub_page

# --- IMAGE HUBS ---
try:
    from ui.pages.image.conversion_hub_page import create_conversion_hub_page
    from ui.pages.image.compression_hub_page import create_compression_hub_page
except ImportError:
    from ui.pages.image.conversion.conversion_hub_page import create_conversion_hub_page
    from ui.pages.image.compression.compression_hub_page import create_compression_hub_page

# --- CONVERSION (Searches in root folder or subfolder) ---
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

# --- COMPRESSION (Searches in root folder or subfolder) ---
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

ROUTE_REGISTRY = {
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
    route_info = ROUTE_REGISTRY.get(route_key)
    if route_info and "builder" in route_info:
        return route_info["builder"](page, selected_paths, on_navigate)

    return ft.Text(t("route_not_found", route_key=route_key), color="red")