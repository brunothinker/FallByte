"""Shared assertion helpers for UI controller tests."""

from unittest.mock import MagicMock

import flet as ft

from ui.controllers.base_controller import JobUI
from ui.i18n import t


def make_job_ui(page) -> JobUI:
    """Builds a `JobUI` whose status label, progress bar and button are spec'd mocks."""
    return JobUI(
        page=page,
        lbl_status=MagicMock(spec=ft.Text),
        progress_bar=MagicMock(spec=ft.ProgressBar),
        btn_action=MagicMock(spec=ft.Button),
    )


def assert_idle_ui(c) -> None:
    """Controller and button must be back to the idle (ready) state."""
    assert c.controller.is_processing is False, (
        "[ui] Controller must reset is_processing to False after execution finishes."
    )
    assert c.controller.abort_requested is False, (
        "[ui] Controller must reset abort_requested to False when returning to idle state."
    )
    assert c.btn_action.content == t("btn_process"), (
        "[ui] Action button label must revert to translated 'btn_process' in idle state."
    )
    assert c.btn_action.bgcolor is not None, (
        "[ui] Action button background color must be restored when returning to idle state."
    )
    assert c.page.data.get("is_processing") is False


def trigger_click(handler, event=None) -> None:
    """Invokes a Flet ControlEventHandler safely without Pyright union-overload issues."""
    from typing import Any, cast
    from unittest.mock import MagicMock

    assert callable(handler), f"Expected callable event handler, got {handler!r}"
    cast(Any, handler)(MagicMock() if event is None else event)
