"""Exercise the Back row in the actual tool layout while a batch runs."""

import threading
from unittest.mock import Mock

import flet as ft
import pytest

from ui import app_layout, theme


def walk(control):
    yield control
    for child in control._get_children():
        yield from walk(child)


@pytest.mark.parametrize("palette", ["blue_light", "blue_dark"])
@pytest.mark.parametrize("outcome", ["success", "failure", "cancel"])
def test_back_row_follows_batch(ctx, monkeypatch, palette, outcome):
    page = ctx.page
    session = {}
    page.session.get.side_effect = session.get
    page.session.set.side_effect = session.__setitem__
    monkeypatch.setattr(theme, "CURRENT_THEME_KEY", palette)
    monkeypatch.setattr(ft.Control, "update", lambda self: None)
    monkeypatch.setattr(threading.Thread, "start", threading.Thread.run)

    route = ctx.spec["id"].replace("-", "_")
    (ctx.in_dir / ctx.spec["in_name"]).touch()
    ctx.controller.selected_input = ctx.in_dir
    ctx.controller.selected_output_dir = ctx.out_dir
    monkeypatch.setattr(
        f"ui.pages.{route}_page.{ctx.spec['cls']}", lambda: ctx.controller
    )
    builder = Mock(wraps=app_layout.build_page_view)
    monkeypatch.setattr(app_layout, "build_page_view", builder)
    layout = app_layout.create_app_layout(page, {})
    navigate = builder.call_args.kwargs["on_navigate"]
    navigate(route)

    back_row = next(
        c
        for c in walk(layout)
        if isinstance(c, ft.Container)
        and isinstance(c.content, ft.ElevatedButton)
        and c.content.icon == ft.icons.ARROW_BACK
    )
    action = next(
        c
        for c in walk(layout)
        if isinstance(c, ft.ElevatedButton) and c.icon == ft.icons.PLAY_ARROW
    )
    assert back_row.visible and back_row.content.visible
    observations = []

    def run_engine(**kwargs):
        observations.append((back_row.visible, action.icon))
        if outcome == "failure":
            raise OSError("test batch failed")
        if outcome == "cancel":
            action.on_click(None)
            page.dialog.actions[1].on_click(None)
            observations.append((back_row.visible, kwargs["cancel_event"].is_set()))
            return {"cancelled": True}
        return {"success": 1, "total_files": 1}

    monkeypatch.setattr(ctx.module, ctx.spec["dir_engine"], run_engine)
    action.on_click(None)

    expected = [(False, ft.icons.STOP)]
    if outcome == "cancel":
        expected.append((False, True))
    assert observations == expected
    assert back_row.visible and back_row.content.visible
    assert action.icon == ft.icons.PLAY_ARROW
