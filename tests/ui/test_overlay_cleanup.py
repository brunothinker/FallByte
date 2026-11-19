"""Regression tests for stale FilePicker accumulation in the page overlay.

Media tool pages create fresh FilePicker controls on every view build. The
router clears them from ``page.overlay`` before rendering a new view, so
repeated view rebuilds (navigation and theme/language changes) cannot leak
orphaned pickers.
"""

from collections.abc import Callable
from unittest.mock import MagicMock

import flet as ft

from ui import app_layout
from ui.app_layout import remove_stale_filepickers


def _pickers(overlay: list[ft.Control]) -> list[ft.FilePicker]:
    return [c for c in overlay if isinstance(c, ft.FilePicker)]


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
    """update_view drops the previous view's pickers before building a new one.

    Every view rebuild funnels through update_view, including theme/language
    changes that bypass cleanup_page_overlays. Calling the centralized helper
    at the top of update_view keeps the overlay bounded on every rebuild.
    """
    captured: dict[str, Callable[[str], None] | None] = {"on_navigate": None}
    calls = {"cleanup": 0}
    real_helper = remove_stale_filepickers

    def tracking_cleanup(page: ft.Page) -> None:
        calls["cleanup"] += 1
        real_helper(page)

    def fake_build(route_key, page, selected_paths, on_navigate):
        captured["on_navigate"] = on_navigate
        # A media page build registers three fresh pickers.
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

    # Drive repeated rebuilds through the real navigation callback. Without
    # the fix, each rebuild adds three more pickers and the overlay grows.
    before = calls["cleanup"]
    for step in range(8):
        route = "image_conversion" if step % 2 == 0 else "video_conversion"
        captured["on_navigate"](route)
        # Exactly one set survives: the freshly built pickers.
        assert len(_pickers(page.overlay)) == 3, (
            f"picker count grew at rebuild {step}: "
            f"{len(_pickers(page.overlay))}"
        )
    assert calls["cleanup"] > before
