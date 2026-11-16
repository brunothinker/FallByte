"""Characterization tests for single-file and batch execution flows across all UI controllers."""

import sys

from tests.ui.helpers import assert_idle_ui
from ui.i18n import t
from ui.theme import get_color

BATCH_OK = {
    "success": 2,
    "failed": 1,
    "total_files": 3,
    "elapsed_seconds": 1.0,
    "original_bytes": 100,
    "compressed_bytes": 50,
    "cancelled": False,
    "cleaned_files_count": 0,
}


def test_single_file_success(ctx):
    """A successful single-file run shows one OK summary and restores the idle UI."""
    ctx.fake_file_engine(ok=True)
    ctx.run_single()

    ctx.summary_dialog.assert_called_once()
    payload = ctx.summary_payload()
    assert payload["success"] == 1, (
        "[ui] Successful single-file summary payload must report success == 1."
    )
    assert payload["failed"] == 0, (
        "[ui] Successful single-file summary payload must report failed == 0."
    )
    assert payload["total_files"] == 1, (
        "[ui] Single-file summary payload must report total_files == 1."
    )
    assert "[OK]" in payload["terminal_log"], (
        "[ui] Single-file success terminal log must contain an '[OK]' entry."
    )
    assert ctx.lbl_status.value == t("msg_success"), (
        "[ui] Status label must show translated 'msg_success' after single-file completion."
    )
    assert_idle_ui(ctx)


def test_single_file_failure(ctx):
    """A failed single-file run reports one failure, logs [FAIL] and shows the error status."""
    ctx.fake_file_engine(ok=False)
    ctx.run_single()

    payload = ctx.summary_payload()
    assert payload["success"] == 0, (
        "[ui] Failed single-file summary payload must report success == 0."
    )
    assert payload["failed"] == 1, (
        "[ui] Failed single-file summary payload must report failed == 1."
    )
    assert "[FAIL]" in payload["terminal_log"], (
        "[ui] Failed single-file terminal log must contain a '[FAIL]' tag."
    )
    assert "[OK]" not in payload["terminal_log"], (
        "[ui] Failed single-file terminal log must not contain a false-positive '[OK]' tag."
    )
    assert ctx.lbl_status.value == t("msg_error"), (
        "[ui] Status label must show translated 'msg_error' when single-file processing fails."
    )
    assert_idle_ui(ctx)


def test_single_file_engine_exception_is_reported_as_failure(ctx):
    """An exception raised by the engine is reported as a failure, never propagated."""
    ctx.fake_file_engine(raises=RuntimeError("boom"))
    ctx.run_single()

    payload = ctx.summary_payload()
    assert payload["failed"] == 1, (
        "[ui] Unhandled engine exception during single-file run must be recorded as failed == 1."
    )
    assert "[ERROR]" in payload["terminal_log"], (
        "[ui] Engine exception during single-file run must log an '[ERROR]' diagnostic line."
    )
    assert_idle_ui(ctx)


def test_single_file_sets_stop_button_while_running(ctx):
    """While the engine runs, the button is in STOP state and the session is flagged as processing."""
    seen = {}

    def fake(**kwargs):
        seen["text"] = ctx.btn_action.text
        seen["bgcolor"] = ctx.btn_action.bgcolor
        seen["color"] = ctx.btn_action.color
        seen["processing"] = ctx.controller.is_processing
        seen["session"] = ctx.page.session.set.call_args
        kwargs["output_path"].parent.mkdir(parents=True, exist_ok=True)
        kwargs["output_path"].write_bytes(b"out")
        return True

    setattr(ctx.module, ctx.spec["file_engine"], fake)
    ctx.run_single()

    assert seen["text"] == t("btn_stop_process"), (
        "[ui] Action button text must switch to translated 'btn_stop_process' while engine is running."
    )
    assert seen["bgcolor"] == get_color("danger"), (
        "[ui] Action button background must switch to 'danger' color while engine is running."
    )
    assert seen["color"] == "#FFFFFF", (
        "[ui] Action button foreground text color must be '#FFFFFF' in active STOP state."
    )
    assert seen["processing"] is True, (
        "[ui] Controller must set is_processing=True while executing the file engine."
    )
    assert seen["session"].args == ("is_processing", True), (
        "[ui] Controller must lock page session navigation via session.set('is_processing', True)."
    )


def test_batch_success_shows_summary_and_restores_ui(ctx):
    """A finished batch shows the summary dialog, full progress and restores the idle UI."""
    ctx.fake_dir_engine(BATCH_OK)
    ctx.run_batch()

    ctx.summary_dialog.assert_called_once()
    assert ctx.progress_bar.value == 1.0, (
        "[ui] Progress bar must reach 1.0 (100%) upon batch completion."
    )
    assert ctx.lbl_status.value == t(
        "msg_success_summary", msg=t("msg_success"), successful=2, total=3
    ), "[ui] Status label must display the formatted 'X of Y' batch completion summary."
    assert "terminal_log" in ctx.summary_payload(), (
        "[ui] Batch summary payload must include captured terminal_log output."
    )
    assert_idle_ui(ctx)


def test_batch_cancelled_reports_cleaned_count_without_summary(ctx):
    """A cancelled batch reports the cleaned file count and shows no summary dialog."""
    ctx.fake_dir_engine({**BATCH_OK, "cancelled": True, "cleaned_files_count": 3})
    ctx.run_batch()

    ctx.summary_dialog.assert_not_called()
    assert ctx.lbl_status.value == t("msg_process_cancelled", count=3), (
        "[ui] Cancelled batch must report the cleaned file count in the status label."
    )
    assert ctx.progress_bar.visible is False, (
        "[ui] Progress bar must be hidden when a batch job is cancelled."
    )
    assert_idle_ui(ctx)


def test_batch_engine_exception_restores_ui_without_summary(ctx):
    """An engine crash during a batch restores the idle UI, shows an error status and no summary dialog."""
    ctx.fake_dir_engine(raises=RuntimeError("boom"))
    ctx.run_batch()

    ctx.summary_dialog.assert_not_called()
    assert ctx.lbl_status.value == t("msg_error"), (
        "[ui] Batch engine crash must display translated 'msg_error' status without opening summary dialog."
    )
    assert_idle_ui(ctx)


def test_batch_restores_standard_streams(ctx):
    """sys.stdout and sys.stderr are restored after the log redirector finishes."""
    before = (sys.stdout, sys.stderr)
    ctx.fake_dir_engine(BATCH_OK)
    ctx.run_batch()
    assert (sys.stdout, sys.stderr) == before, (
        "[ui] Batch execution must restore original sys.stdout and sys.stderr streams in finally block."
    )
