import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import flet as ft

from ui.pages.audio_compression_page import create_audio_compression_page
from ui.pages.audio_conversion_page import create_audio_conversion_page
from ui.pages.audio_extraction_page import create_audio_extraction_page
from ui.pages.audio_normalization_page import create_audio_normalization_page
from ui.pages.home_page import create_home_page
from ui.pages.image_compression_page import create_compression_page
from ui.pages.image_conversion_page import create_conversion_page
from ui.pages.image_metadata_page import create_image_metadata_page
from ui.pages.image_resize_page import create_image_resize_page
from ui.pages.media_hub_page import create_media_hub_page
from ui.pages.video_compression_page import create_video_compression_page
from ui.pages.video_conversion_page import create_video_conversion_page
from ui.pages.video_downscale_page import create_video_downscale_page
from ui.pages.video_tracks_page import create_video_tracks_page

# Setup module logger
logger = logging.getLogger(__name__)


@dataclass
class ModuleOption:
    """Represents a child feature option card inside a media hub module."""

    id: str
    title_key: str
    desc_key: str
    icon: str
    route_key: str
    builder: Callable[..., ft.Control]


@dataclass
class ModuleDefinition:
    """Central registry definition for a top-level application module."""

    id: str
    title_key: str
    desc_key: str
    icon: str
    sidebar_icon: str
    route_key: str
    builder: Callable[..., ft.Control]
    options: list[ModuleOption]


# Centralized registry mapping module IDs to their structural definitions
MODULE_REGISTRY: list[ModuleDefinition] = [
    ModuleDefinition(
        id="image",
        title_key="home_mod_image_title",
        desc_key="home_mod_image_desc",
        icon=ft.icons.IMAGE,
        sidebar_icon=ft.icons.IMAGE_OUTLINED,
        route_key="image_hub",
        builder=lambda page, paths, navigate: create_media_hub_page(
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
                {
                    "title_key": "image_hub_card_resize_title",
                    "desc_key": "image_hub_card_resize_desc",
                    "icon": ft.icons.PHOTO_SIZE_SELECT_LARGE,
                    "route_key": "image_resize",
                },
                {
                    "title_key": "image_hub_card_metadata_title",
                    "desc_key": "image_hub_card_metadata_desc",
                    "icon": ft.icons.PRIVACY_TIP_OUTLINED,
                    "route_key": "image_metadata",
                },
            ],
        ),
        options=[
            ModuleOption(
                id="image_conversion",
                title_key="image_hub_card_conversion_title",
                desc_key="image_hub_card_conversion_desc",
                icon=ft.icons.TRANSFORM,
                route_key="image_conversion",
                builder=create_conversion_page,
            ),
            ModuleOption(
                id="image_compression",
                title_key="image_hub_card_compression_title",
                desc_key="image_hub_card_compression_desc",
                icon=ft.icons.COMPRESS,
                route_key="image_compression",
                builder=create_compression_page,
            ),
            ModuleOption(
                id="image_resize",
                title_key="image_hub_card_resize_title",
                desc_key="image_hub_card_resize_desc",
                icon=ft.icons.PHOTO_SIZE_SELECT_LARGE,
                route_key="image_resize",
                builder=create_image_resize_page,
            ),
            ModuleOption(
                id="image_metadata",
                title_key="image_hub_card_metadata_title",
                desc_key="image_hub_card_metadata_desc",
                icon=ft.icons.PRIVACY_TIP_OUTLINED,
                route_key="image_metadata",
                builder=create_image_metadata_page,
            ),
        ],
    ),
    ModuleDefinition(
        id="video",
        title_key="home_mod_video_title",
        desc_key="home_mod_video_desc",
        icon=ft.icons.VIDEO_LIBRARY,
        sidebar_icon=ft.icons.VIDEO_LIBRARY_OUTLINED,
        route_key="video_hub",
        builder=lambda page, paths, navigate: create_media_hub_page(
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
                {
                    "title_key": "video_hub_card_downscale_title",
                    "desc_key": "video_hub_card_downscale_desc",
                    "icon": ft.icons.ASPECT_RATIO,
                    "route_key": "video_downscale",
                },
                {
                    "title_key": "video_hub_card_tracks_title",
                    "desc_key": "video_hub_card_tracks_desc",
                    "icon": ft.icons.SUBTITLES,
                    "route_key": "video_tracks",
                },
            ],
        ),
        options=[
            ModuleOption(
                id="video_conversion",
                title_key="video_hub_card_conversion_title",
                desc_key="video_hub_card_conversion_desc",
                icon=ft.icons.TRANSFORM,
                route_key="video_conversion",
                builder=create_video_conversion_page,
            ),
            ModuleOption(
                id="video_compression",
                title_key="video_hub_card_compression_title",
                desc_key="video_hub_card_compression_desc",
                icon=ft.icons.COMPRESS,
                route_key="video_compression",
                builder=create_video_compression_page,
            ),
            ModuleOption(
                id="video_downscale",
                title_key="video_hub_card_downscale_title",
                desc_key="video_hub_card_downscale_desc",
                icon=ft.icons.ASPECT_RATIO,
                route_key="video_downscale",
                builder=create_video_downscale_page,
            ),
            ModuleOption(
                id="video_tracks",
                title_key="video_hub_card_tracks_title",
                desc_key="video_hub_card_tracks_desc",
                icon=ft.icons.SUBTITLES,
                route_key="video_tracks",
                builder=create_video_tracks_page,
            ),
        ],
    ),
    ModuleDefinition(
        id="audio",
        title_key="home_mod_audio_title",
        desc_key="home_mod_audio_desc",
        icon=ft.icons.HEADPHONES,
        sidebar_icon=ft.icons.HEADPHONES_OUTLINED,
        route_key="audio_hub",
        builder=lambda page, paths, navigate: create_media_hub_page(
            page=page,
            selected_paths=paths,
            on_navigate=navigate,
            main_icon=ft.icons.HEADPHONES_OUTLINED,
            heading_key="audio_hub_heading",
            subheading_key="audio_hub_subheading",
            options=[
                {
                    "title_key": "audio_hub_card_conversion_title",
                    "desc_key": "audio_hub_card_conversion_desc",
                    "icon": ft.icons.TRANSFORM,
                    "route_key": "audio_conversion",
                },
                {
                    "title_key": "audio_hub_card_compression_title",
                    "desc_key": "audio_hub_card_compression_desc",
                    "icon": ft.icons.COMPRESS,
                    "route_key": "audio_compression",
                },
                {
                    "title_key": "audio_hub_card_extraction_title",
                    "desc_key": "audio_hub_card_extraction_desc",
                    "icon": ft.icons.AUDIOTRACK,
                    "route_key": "audio_extraction",
                },
                {
                    "title_key": "audio_hub_card_normalization_title",
                    "desc_key": "audio_hub_card_normalization_desc",
                    "icon": ft.icons.EQUALIZER,
                    "route_key": "audio_normalization",
                },
            ],
        ),
        options=[
            ModuleOption(
                id="audio_conversion",
                title_key="audio_hub_card_conversion_title",
                desc_key="audio_hub_card_conversion_desc",
                icon=ft.icons.TRANSFORM,
                route_key="audio_conversion",
                builder=create_audio_conversion_page,
            ),
            ModuleOption(
                id="audio_compression",
                title_key="audio_hub_card_compression_title",
                desc_key="audio_hub_card_compression_desc",
                icon=ft.icons.COMPRESS,
                route_key="audio_compression",
                builder=create_audio_compression_page,
            ),
            ModuleOption(
                id="audio_extraction",
                title_key="audio_hub_card_extraction_title",
                desc_key="audio_hub_card_extraction_desc",
                icon=ft.icons.AUDIOTRACK,
                route_key="audio_extraction",
                builder=create_audio_extraction_page,
            ),
            ModuleOption(
                id="audio_normalization",
                title_key="audio_hub_card_normalization_title",
                desc_key="audio_hub_card_normalization_desc",
                icon=ft.icons.EQUALIZER,
                route_key="audio_normalization",
                builder=create_audio_normalization_page,
            ),
        ],
    ),
]


def get_all_routes() -> dict[str, dict[str, Any]]:
    """Builds a lookup mapping route keys to view builder callbacks and title keys."""
    routes: dict[str, dict[str, Any]] = {
        "home": {
            "title_key": "home_header_title",
            "builder": create_home_page,
        }
    }

    for mod in MODULE_REGISTRY:
        routes[mod.route_key] = {
            "title_key": mod.title_key,
            "builder": mod.builder,
        }
        for opt in mod.options:
            routes[opt.route_key] = {
                "title_key": opt.title_key,
                "builder": opt.builder,
            }

    return routes


def resolve_active_module_id(current_route: str) -> str:
    """Resolves the top-level module ID matching the active route without prefix splitting."""
    if current_route == "home":
        return "home"

    for mod in MODULE_REGISTRY:
        if current_route == mod.route_key:
            return mod.id
        for opt in mod.options:
            if current_route == opt.route_key:
                return mod.id

    return ""


def resolve_parent_route(current_route: str) -> str | None:
    """Resolves the deterministic parent route in the module hierarchy.

    Returns None when already at 'home' or when no parent applies.
    """
    if not current_route or current_route == "home":
        return None

    for mod in MODULE_REGISTRY:
        if current_route == mod.route_key:
            return "home"
        for opt in mod.options:
            if current_route == opt.route_key:
                return mod.route_key

    normalized = current_route.strip("/")
    for mod in MODULE_REGISTRY:
        mod_slug = mod.route_key.removesuffix("_hub").strip("/")
        if normalized.startswith(f"{mod_slug}/") or normalized.startswith(f"{mod_slug}_"):
            return mod.route_key

    return "home"
