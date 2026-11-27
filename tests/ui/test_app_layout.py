"""UI: app_layout, registry, router, state persistence, sidebar, and back button."""

from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import flet as ft
import pytest

from src.video.utils.video_ffmpeg_utils import MediaTrack
from ui import app_layout, i18n, theme
from ui.app_layout import (
    SIDEBAR_COLLAPSED_WIDTH,
    SIDEBAR_EXPANDED_WIDTH,
    _extract_submodules,
    _resolve_icon_path,
    remove_stale_filepickers,
)
from ui.registry import MODULE_REGISTRY, resolve_parent_route
from ui.router import build_page_view


def _pickers(overlay: list[ft.Control]) -> list[ft.FilePicker]:
    return [c for c in overlay if isinstance(c, ft.FilePicker)]


def _find_controls(
    root: ft.Control | None, predicate: Callable[[ft.Control], bool]
) -> list[ft.Control]:
    """Recursively collects Flet controls matching a predicate."""
    found: list[ft.Control] = []
    if root is None:
        return found
    if predicate(root):
        found.append(root)
    content = getattr(root, "content", None)
    if isinstance(content, ft.Control):
        found.extend(_find_controls(content, predicate))
    for attr in ("controls", "actions"):
        children = getattr(root, attr, None)
        if isinstance(children, list):
            for child in children:
                if isinstance(child, ft.Control):
                    found.extend(_find_controls(child, predicate))
    return found


def test_remove_stale_filepickers_clears_only_pickers(mock_page):
    """Only FilePicker controls are removed; unrelated overlays are preserved."""
    stale = [ft.FilePicker() for _ in range(3)]
    dialog = ft.AlertDialog(title=ft.Text("keep me"))
    mock_page.overlay.extend([*stale, dialog])

    remove_stale_filepickers(mock_page)

    assert _pickers(mock_page.overlay) == []
    assert dialog in mock_page.overlay
    assert len(mock_page.overlay) == 1


def test_update_view_clears_stale_pickers_before_rebuild(monkeypatch):
    """update_view drops the previous view's pickers before building a new one."""
    captured: dict[str, Callable[[str], None] | None] = {"on_navigate": None}
    calls = {"cleanup": 0}
    real_helper = remove_stale_filepickers

    def tracking_cleanup(page: ft.Page) -> None:
        calls["cleanup"] += 1
        real_helper(page)

    def fake_build(route_key, page, selected_paths, on_navigate):
        captured["on_navigate"] = on_navigate
        page.overlay.extend([ft.FilePicker() for _ in range(3)])
        return ft.Container()

    monkeypatch.setattr(app_layout, "remove_stale_filepickers", tracking_cleanup)
    monkeypatch.setattr(app_layout, "build_page_view", fake_build)

    page = MagicMock()
    page.route = "/"
    page.overlay = []
    page.dialog = None
    page.session.get.return_value = False

    layout = app_layout.create_app_layout(page, {}, "test")
    assert layout is not None
    assert calls["cleanup"] == 1
    assert len(_pickers(page.overlay)) == 3
    assert captured["on_navigate"] is not None

    before = calls["cleanup"]
    for step in range(8):
        route = "image_conversion" if step % 2 == 0 else "video_conversion"
        captured["on_navigate"](route)
        assert len(_pickers(page.overlay)) == 3
    assert calls["cleanup"] > before


def test_module_registry_route_and_active_state_resolution():
    """Verifies route resolution and active module matching using module IDs."""
    from ui.registry import get_all_routes, resolve_active_module_id

    routes = get_all_routes()
    for route in (
        "home",
        "image_hub",
        "video_hub",
        "audio_hub",
        "image_conversion",
        "image_compression",
        "image_resize",
        "image_metadata",
        "video_conversion",
        "video_compression",
        "video_downscale",
        "video_tracks",
        "audio_conversion",
        "audio_compression",
        "audio_extraction",
        "audio_normalization",
    ):
        assert route in routes

    assert resolve_active_module_id("home") == "home"
    assert resolve_active_module_id("image_hub") == "image"
    assert resolve_active_module_id("image_conversion") == "image"
    assert resolve_active_module_id("image_resize") == "image"
    assert resolve_active_module_id("image_metadata") == "image"
    assert resolve_active_module_id("video_compression") == "video"
    assert resolve_active_module_id("audio_hub") == "audio"
    assert resolve_active_module_id("audio_normalization") == "audio"
    assert resolve_active_module_id("unknown_route") == ""


def test_extract_submodules_reads_module_definition_options():
    """_extract_submodules extracts route, title_key, and icon directly from ModuleDefinition."""
    for mod in MODULE_REGISTRY:
        extracted = _extract_submodules(mod)
        assert len(extracted) == len(mod.options)
        for item, opt in zip(extracted, mod.options, strict=True):
            assert item == {
                "route": opt.route_key,
                "title_key": opt.title_key,
                "icon": opt.icon,
            }


@pytest.mark.parametrize(
    ("theme_key", "expected_stem"),
    [
        ("blue_dark", "blue.png"),
        ("purple_light", "purple.png"),
        ("emerald_dark", "green.png"),
        ("emerald_light", "green.png"),
        ("red_dark", "red.png"),
        ("amber_light", "amber.png"),
        ("nonexistent_theme", "fallbyte_icon.png"),
    ],
)
def test_resolve_icon_path_maps_themes_and_fallbacks(theme_key, expected_stem):
    """_resolve_icon_path resolves theme-matched icons and falls back cleanly."""
    resolved = Path(_resolve_icon_path(theme_key))
    assert resolved.name == expected_stem
    assert resolved.exists()


def test_state_persists_across_theme_and_language_rebuild(tmp_workspace, mock_page):
    """Paths and tool options survive theme/language modal apply rebuilds."""
    in_dir, out_dir = tmp_workspace
    sample_img = in_dir / "sample.png"
    sample_img.write_bytes(b"png")

    selected_paths: dict = {}
    layout = app_layout.create_app_layout(mock_page, selected_paths, "test")

    # Navigate to image_compression via a nav card
    img_hub_card = _find_controls(
        layout,
        lambda c: isinstance(c, ft.Container) and callable(getattr(c, "on_click", None)),
    )
    assert img_hub_card

    # Pre-seed persisted state as if user selected paths and modified options
    selected_paths["image_compression"] = {
        "input_path": sample_img,
        "output_dir": out_dir,
        "options": {"quality": 42, "strip_metadata": True},
    }

    # Build view, mutate widgets, trigger save_view_state, and rebuild after theme/lang change
    view = build_page_view("image_compression", mock_page, selected_paths, lambda _: None)
    sliders = _find_controls(view, lambda c: isinstance(c, ft.Slider))
    checkboxes = _find_controls(view, lambda c: isinstance(c, ft.Checkbox))
    texts = _find_controls(view, lambda c: isinstance(c, ft.Text))

    assert sliders[0].value == 42
    assert checkboxes[0].value is True
    assert any(t.value == sample_img.name for t in texts)
    assert any(t.value == out_dir.name for t in texts)

    # Simulate user tweaking controls before switching theme/language
    sliders[0].value = 65
    checkboxes[0].value = False
    mock_page.data["save_view_state"]()

    assert selected_paths["image_compression"]["options"] == {
        "quality": 65,
        "strip_metadata": False,
    }

    # Switch theme and language, then rebuild view
    prev_theme = theme.CURRENT_THEME_KEY
    prev_lang = i18n.CURRENT_LANG
    try:
        theme.set_active_theme("red_light")
        i18n.set_language("pt")
        rebuilt = build_page_view(
            "image_compression", mock_page, selected_paths, lambda _: None
        )
        rebuilt_sliders = _find_controls(rebuilt, lambda c: isinstance(c, ft.Slider))
        rebuilt_checkboxes = _find_controls(
            rebuilt, lambda c: isinstance(c, ft.Checkbox)
        )
        rebuilt_texts = _find_controls(rebuilt, lambda c: isinstance(c, ft.Text))

        assert rebuilt_sliders[0].value == 65
        assert rebuilt_checkboxes[0].value is False
        assert any(t.value == sample_img.name for t in rebuilt_texts)
        assert any(t.value == out_dir.name for t in rebuilt_texts)
    finally:
        theme.set_active_theme(prev_theme)
        i18n.set_language(prev_lang)


@pytest.mark.parametrize(
    ("route_key", "saved_options", "expected_saved"),
    [
        (
            "image_conversion",
            {"target_format": "WEBP", "color_key": "color_black"},
            {"target_format": "WEBP", "color_key": "color_black"},
        ),
        (
            "image_resize",
            {
                "mode": "percentage",
                "max_width": "800",
                "max_height": "600",
                "percentage": "35",
            },
            {
                "mode": "percentage",
                "max_width": "800",
                "max_height": "600",
                "percentage": "35",
            },
        ),
        (
            "video_downscale",
            {"resolution": "480p"},
            {"resolution": "480p"},
        ),
        (
            "audio_normalization",
            {"preset": "podcast"},
            {"preset": "podcast"},
        ),
    ],
)
def test_tool_pages_restore_and_resave_options(
    tmp_workspace, mock_page, route_key, saved_options, expected_saved
):
    """All stateful tool pages restore saved options and re-export them via save_view_state."""
    in_dir, out_dir = tmp_workspace
    selected_paths: dict = {
        route_key: {
            "input_path": in_dir,
            "output_dir": out_dir,
            "options": dict(saved_options),
        }
    }

    build_page_view(route_key, mock_page, selected_paths, lambda _: None)
    assert callable(mock_page.data.get("save_view_state"))

    mock_page.data["save_view_state"]()
    assert selected_paths[route_key]["input_path"] == in_dir
    assert selected_paths[route_key]["output_dir"] == out_dir
    assert selected_paths[route_key]["options"] == expected_saved


def test_video_tracks_page_restores_checked_stream_indices(tmp_workspace, mock_page):
    """video_tracks page restores previously checked stream indices after rebuild."""
    in_dir, out_dir = tmp_workspace
    video_file = in_dir / "movie.mkv"
    video_file.write_bytes(b"mkv")

    fake_audio = [
        MediaTrack(stream_index=1, track_type="audio", codec="aac", language="eng", title=""),
        MediaTrack(stream_index=2, track_type="audio", codec="aac", language="por", title=""),
    ]
    fake_subs = [
        MediaTrack(stream_index=3, track_type="subtitle", codec="subrip", language="por", title=""),
    ]

    selected_paths: dict = {
        "video_tracks": {
            "input_path": video_file,
            "output_dir": out_dir,
            "options": {"selected_indices": [2]},
        }
    }

    with patch(
        "ui.controllers.video_tracks_controller.inspect_video_tracks",
        return_value=(fake_audio, fake_subs),
    ):
        view = build_page_view("video_tracks", mock_page, selected_paths, lambda _: None)
        checkboxes = _find_controls(view, lambda c: isinstance(c, ft.Checkbox))
        checked_labels = [cb.label for cb in checkboxes if cb.value]
        assert len(checked_labels) == 1
        assert "POR" in checked_labels[0].upper()

        mock_page.data["save_view_state"]()
        assert selected_paths["video_tracks"]["options"] == {"selected_indices": [2]}


def test_missing_persisted_paths_are_ignored_on_restore(tmp_path, mock_page):
    """Deleted files/folders in selected_paths are ignored safely without crashing."""
    missing_file = tmp_path / "deleted.png"
    missing_dir = tmp_path / "deleted_out"
    selected_paths: dict = {
        "image_metadata": {
            "input_path": missing_file,
            "output_dir": missing_dir,
            "options": {},
        }
    }

    view = build_page_view("image_metadata", mock_page, selected_paths, lambda _: None)
    mock_page.data["save_view_state"]()
    assert view is not None
    assert selected_paths["image_metadata"]["input_path"] is None
    assert selected_paths["image_metadata"]["output_dir"] is None


def test_sidebar_collapse_and_keyboard_back_navigation(mock_page):
    """Sidebar toggles width and Escape navigates up the hierarchy unless processing."""
    layout = app_layout.create_app_layout(mock_page, {}, "test")
    row = layout.content.controls[0]
    sidebar = row.controls[0]

    # Starts collapsed by default
    assert sidebar.width == SIDEBAR_COLLAPSED_WIDTH

    # Simulate mounted Flet page and synchronous run_task for sidebar animation
    scheduled = []
    mock_page.run_task = lambda fn, *a: scheduled.append(fn(*a))
    with patch.object(ft.Container, "page", new=mock_page):
        brand_col = sidebar.content.controls[0].content
        btn_expand_icon = brand_col.controls[0]
        btn_expand_icon.on_click(MagicMock())
        assert sidebar.width == SIDEBAR_EXPANDED_WIDTH
    for coro in scheduled:
        coro.close()

    # Navigate into image_hub -> image_conversion via nav card click
    content_stack = row.controls[1]
    main_col = content_stack.controls[0]
    content_area = main_col.controls[0]
    bottom_back_bar = main_col.controls[1]

    # On home, back bar is hidden
    assert bottom_back_bar.visible is False
    assert resolve_parent_route("image_conversion") == "image_hub"
    assert resolve_parent_route("image_hub") == "home"

    # Click first module card on home ("Image Tools")
    home_cards = _find_controls(
        content_area,
        lambda c: isinstance(c, ft.Container) and callable(getattr(c, "on_click", None)),
    )
    home_cards[0].on_click(MagicMock())
    assert bottom_back_bar.visible is True

    # Lock navigation while processing: Escape must do nothing
    mock_page.data["is_processing"] = True
    mock_page.on_keyboard_event(
        MagicMock(key="Escape")
    )
    assert bottom_back_bar.visible is True

    # Unlock and press Escape -> returns to home and hides back bar
    mock_page.data["is_processing"] = False
    mock_page.on_keyboard_event(
        MagicMock(key="Escape")
    )
    assert bottom_back_bar.visible is False
