"""UI: theme_dialog and language_dialog."""

import asyncio
from unittest.mock import MagicMock

import flet as ft

from ui import i18n
from ui.components import language_dialog, theme_dialog
from ui.theme import THEME_PRESETS


def _collect_clickable_containers(root: ft.Control) -> list[ft.Container]:
    """Recursively collects all ft.Container instances that expose an on_click handler."""
    found: list[ft.Container] = []

    def walk(ctrl: ft.Control | None) -> None:
        if ctrl is None:
            return
        if isinstance(ctrl, ft.Container) and getattr(ctrl, "on_click", None) is not None:
            found.append(ctrl)
        content = getattr(ctrl, "content", None)
        if isinstance(content, ft.Control):
            walk(content)
        for child in getattr(ctrl, "controls", None) or []:
            walk(child)

    walk(root)
    return found


def test_theme_modal_close_and_apply_selection(mock_page, monkeypatch) -> None:
    """Builds theme modal, handles close callback, and applies/persists a newly selected theme."""
    persisted: dict[str, str] = {}
    applied_themes: list[str] = []
    scheduled_coros: list = []

    monkeypatch.setattr(
        theme_dialog, "get_config_value", lambda _k, default=None: "blue_dark"
    )
    monkeypatch.setattr(
        theme_dialog, "set_config_value", persisted.__setitem__
    )
    monkeypatch.setattr(
        theme_dialog, "set_active_theme", applied_themes.append
    )
    mock_page.run_task = MagicMock(
        side_effect=lambda fn, *a: scheduled_coros.append(fn(*a))
    )

    on_close = MagicMock()
    on_applied = MagicMock()

    card = theme_dialog.build_theme_modal(
        mock_page, on_close=on_close, on_applied=on_applied
    )
    assert isinstance(card, ft.Container), (
        "[ui] build_theme_modal() must return an ft.Container card."
    )

    header_row = card.content.controls[0]  # type: ignore[union-attr]
    btn_close = header_row.controls[1]
    assert isinstance(btn_close, ft.IconButton)
    btn_close.on_click(MagicMock())
    on_close.assert_called_once()

    clickables = _collect_clickable_containers(card)
    tiles = [c for c in clickables if c is not card]
    assert len(tiles) == len(THEME_PRESETS), (
        "[ui] Theme modal must render one clickable tile per entry in THEME_PRESETS."
    )

    dark_keys = [k for k in THEME_PRESETS if k.endswith("_dark")]
    light_keys = [k for k in THEME_PRESETS if k.endswith("_light")]
    assert light_keys, "[ui] Expected at least one '_light' preset in THEME_PRESETS."
    target_key = light_keys[0]
    target_index = len(dark_keys) + light_keys.index(target_key)

    card.update = MagicMock()
    tiles[target_index].on_click(MagicMock())
    assert len(scheduled_coros) == 1, (
        "[ui] Selecting a theme tile must schedule the async change task on page."
    )

    async def fast_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(theme_dialog.asyncio, "sleep", fast_sleep)
    asyncio.run(scheduled_coros[0])

    assert applied_themes == [target_key], (
        "[ui] Theme selection task must activate the selected theme."
    )
    assert persisted.get("theme") == target_key, (
        "[ui] Theme selection task must persist 'theme' via set_config_value."
    )
    assert mock_page.theme_mode == ft.ThemeMode.LIGHT, (
        "[ui] Selecting a '_light' theme must switch page.theme_mode to ThemeMode.LIGHT."
    )
    on_applied.assert_called_once()


def test_language_modal_close_and_apply_selection(mock_page, monkeypatch) -> None:
    """Builds language modal, handles close callback, and applies/persists a newly selected language."""
    persisted: dict[str, str] = {}
    applied_langs: list[str] = []
    scheduled_coros: list = []

    monkeypatch.setattr(
        language_dialog, "set_config_value", persisted.__setitem__
    )
    monkeypatch.setattr(
        language_dialog, "set_language", applied_langs.append
    )
    mock_page.run_task = MagicMock(
        side_effect=lambda fn, *a: scheduled_coros.append(fn(*a))
    )

    on_close = MagicMock()
    on_applied = MagicMock()

    card = language_dialog.build_language_modal(
        mock_page, on_close=on_close, on_applied=on_applied
    )
    assert isinstance(card, ft.Container), (
        "[ui] build_language_modal() must return an ft.Container card."
    )

    header_row = card.content.controls[0]  # type: ignore[union-attr]
    btn_close = header_row.controls[1]
    assert isinstance(btn_close, ft.IconButton)
    btn_close.on_click(MagicMock())
    on_close.assert_called_once()

    clickables = _collect_clickable_containers(card)
    tiles = [c for c in clickables if c is not card]
    lang_codes = list(i18n.AVAILABLE_LANGUAGES.keys())
    assert len(tiles) == len(lang_codes), (
        "[ui] Language modal must render one clickable tile per entry in AVAILABLE_LANGUAGES."
    )

    target_index = 1 if len(lang_codes) > 1 else 0
    target_code = lang_codes[target_index]

    card.update = MagicMock()
    tiles[target_index].on_click(MagicMock())
    assert len(scheduled_coros) == 1, (
        "[ui] Selecting a language tile must schedule the async change task on page."
    )

    async def fast_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(language_dialog.asyncio, "sleep", fast_sleep)
    asyncio.run(scheduled_coros[0])

    assert applied_langs == [target_code], (
        "[ui] Language selection task must activate the selected language."
    )
    assert persisted.get("language") == target_code, (
        "[ui] Language selection task must persist 'language' via set_config_value."
    )
    on_applied.assert_called_once()
