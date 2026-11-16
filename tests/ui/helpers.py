"""Shared assertion helpers for UI controller tests."""

from ui.i18n import t


def assert_idle_ui(c) -> None:
    """Controller and button must be back to the idle (ready) state."""
    assert c.controller.is_processing is False, (
        "[ui] Controller must reset is_processing to False after execution finishes."
    )
    assert c.controller.abort_requested is False, (
        "[ui] Controller must reset abort_requested to False when returning to idle state."
    )
    assert c.btn_action.text == t("btn_process"), (
        "[ui] Action button label must revert to translated 'btn_process' in idle state."
    )
    assert c.btn_action.bgcolor is not None, (
        "[ui] Action button background color must be restored when returning to idle state."
    )
    c.page.session.set.assert_any_call("is_processing", False)
