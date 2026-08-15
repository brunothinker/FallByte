import logging
from pathlib import Path
from typing import Any, Callable, Dict
import flet as ft

from ui.i18n import t
from ui.pages.home_page import create_home_page
from ui.pages.image_compression_page import create_compression_page
from ui.pages.image_conversion_page import create_conversion_page
from ui.pages.media_hub_page import create_media_hub_page
from ui.pages.video_compression_page import create_video_compression_page
from ui.pages.video_conversion_page import create_video_conversion_page

# Setup module logger
logger = logging.getLogger(__name__)

# Centralized router registry mapping application routes to title keys and view builders
ROUTE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "home": {
        "title_key": "home_header_title",
        "builder": create_home_page,
    },
    "image_hub": {
        "title_key": "image_hub_header_title",
        "builder": lambda page, paths, navigate: create_media_hub_page(
            page=page,
            selected_paths=paths,
            on_navigate=navigate,
            main_icon=ft.icons.IMAGE_OUTLINED,
            heading_key="image_hub_heading",
            subheading_key="image_hub_subheading",
            options=[
                {
                    "title_key": "image_hub_card_conversion_title",
                    "desc_key": "image_hub_card_conversion_desc",
                    "icon": ft.icons.TRANSFORM,
                    "route_key": "image_conversion",
                },
                {
                    "title_key": "image_hub_card_compression_title",
                    "desc_key": "image_hub_card_compression_desc",
                    "icon": ft.icons.COMPRESS,
                    "route_key": "image_compression",
                },
            ],
        ),
    },
    "image_conversion": {
        "title_key": "image_hub_card_conversion_title",
        "builder": create_conversion_page,
    },
    "image_compression": {
        "title_key": "image_hub_card_compression_title",
        "builder": create_compression_page,
    },
    "video_hub": {
        "title_key": "video_hub_header_title",
        "builder": lambda page, paths, navigate: create_media_hub_page(
            page=page,
            selected_paths=paths,
            on_navigate=navigate,
            main_icon=ft.icons.VIDEO_LIBRARY_OUTLINED,
            heading_key="video_hub_heading",
            subheading_key="video_hub_subheading",
            options=[
                {
                    "title_key": "video_hub_card_conversion_title",
                    "desc_key": "video_hub_card_conversion_desc",
                    "icon": ft.icons.TRANSFORM,
                    "route_key": "video_conversion",
                },
                {
                    "title_key": "video_hub_card_compression_title",
                    "desc_key": "video_hub_card_compression_desc",
                    "icon": ft.icons.COMPRESS,
                    "route_key": "video_compression",
                },
            ],
        ),
    },
    "video_conversion": {
        "title_key": "video_hub_card_conversion_title",
        "builder": create_video_conversion_page,
    },
    "video_compression": {
        "title_key": "video_hub_card_compression_title",
        "builder": create_video_compression_page,
    },
}


def build_page_view(
    route_key: str,
    page: ft.Page,
    selected_paths: Dict[str, Path],
    on_navigate: Callable[[str], None],
) -> ft.Control:
    """Constructs and returns the view component corresponding to a given route key."""
    route_info = ROUTE_REGISTRY.get(route_key)
    if route_info and "builder" in route_info:
        return route_info["builder"](page, selected_paths, on_navigate)

    logger.warning(f"Attempted navigation to unknown route key: '{route_key}'")
    return ft.Text(t("route_not_found", route_key=route_key), color="red")