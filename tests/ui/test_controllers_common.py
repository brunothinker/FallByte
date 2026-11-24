"""UI: parameterized tests across multiple controllers (do not split)."""

import logging
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, Mock

import flet as ft
import pytest

from src.utils.file_result import FileResult
from src.utils.progress import ProgressInfo
from tests.ui.helpers import assert_idle_ui
from ui import app_layout, theme
from ui.i18n import t
from ui.theme import get_color


def walk(control: ft.Control) -> Iterator[ft.Control]:
    yield control
    for child in control._get_children():
        yield from walk(child)


BATCH_OK = {
    "success": 2,
    "skipped": 0,
    "failed": 1,
    "total_files": 3,
    "elapsed_seconds": 1.0,
    "original_bytes": 100,
    "compressed_bytes": 50,
    "cancelled": False,
    "cleaned_files_count": 0,
}


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
    assert isinstance(back_row.content, ft.ElevatedButton)
    assert back_row.visible and back_row.content.visible
    assert action.on_click is not None
    observations: list[tuple[bool | None, object]] = []

    def run_engine(**kwargs):
        observations.append((back_row.visible, action.icon))
        if outcome == "failure":
            raise OSError("test batch failed")
        if outcome == "cancel":
            assert action.on_click is not None
            action.on_click(None)
            confirm_btn = page.dialog.actions[1]
            assert confirm_btn.on_click is not None
            confirm_btn.on_click(None)
            observations.append((back_row.visible, kwargs["cancel_event"].is_set()))
            return {"cancelled": True}
        return {"success": 1, "total_files": 1}

    monkeypatch.setattr(ctx.module, ctx.spec["dir_engine"], run_engine)
    action.on_click(None)

    expected: list[tuple[bool | None, object]] = [(False, ft.icons.STOP)]
    if outcome == "cancel":
        expected.append((False, True))
    assert observations == expected
    assert isinstance(back_row.content, ft.ElevatedButton)
    assert back_row.visible and back_row.content.visible
    assert action.icon == ft.icons.PLAY_ARROW


def test_single_file_success(ctx):
    """A successful single-file run shows one OK summary and restores the idle UI."""
    ctx.fake_file_engine(ok=True)
    ctx.run_single()

    ctx.summary_dialog.assert_called_once()
    payload = ctx.summary_payload()
    assert payload["success"] == 1, (
        "[ui] Successful single-file summary payload must report success == 1."
    )
    assert payload["skipped"] == 0, (
        "[ui] Successful single-file summary payload must report skipped == 0."
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


def test_single_file_skipped(ctx):
    """A skipped single-file run reports skipped == 1, logs [SKIP] and sets warning status."""
    ctx.fake_file_engine(
        result=FileResult.skipped("skip_not_smaller", quality=80)
    )
    ctx.run_single()

    ctx.summary_dialog.assert_called_once()
    payload = ctx.summary_payload()
    assert payload["success"] == 0, (
        "[ui] Skipped single-file summary payload must report success == 0."
    )
    assert payload["skipped"] == 1, (
        "[ui] Skipped single-file summary payload must report skipped == 1."
    )
    assert payload["failed"] == 0, (
        "[ui] Skipped single-file summary payload must report failed == 0."
    )
    assert payload["total_files"] == 1, (
        "[ui] Skipped single-file summary payload must report total_files == 1."
    )
    assert payload["original_bytes"] == 0, (
        "[ui] Skipped single-file summary payload must report original_bytes == 0."
    )
    assert "[SKIP]" in payload["terminal_log"], (
        "[ui] Skipped single-file terminal log must contain a '[SKIP]' tag."
    )
    assert "[OK]" not in payload["terminal_log"], (
        "[ui] Skipped single-file terminal log must not emit an '[OK]' tag."
    )
    assert "[FAIL]" not in payload["terminal_log"], (
        "[ui] Skipped single-file terminal log must not emit a '[FAIL]' tag."
    )
    assert ctx.lbl_status.value == t("msg_kept_original"), (
        "[ui] Status label must show translated 'msg_kept_original' when single-file is skipped."
    )
    assert ctx.lbl_status.color == get_color("warning"), (
        "[ui] Status label must use warning color when single-file is skipped."
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
    assert payload["skipped"] == 0, (
        "[ui] Failed single-file summary payload must report skipped == 0."
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
    if not ctx.spec.get("supports_single", True):
        pytest.skip(f"{ctx.spec['id']} is directory-only.")

    seen = {}

    def fake(**kwargs):
        seen["text"] = ctx.btn_action.text
        seen["bgcolor"] = ctx.btn_action.bgcolor
        seen["color"] = ctx.btn_action.color
        seen["processing"] = ctx.controller.is_processing
        seen["session"] = ctx.page.session.set.call_args
        kwargs["output_path"].parent.mkdir(parents=True, exist_ok=True)
        kwargs["output_path"].write_bytes(b"out")
        return FileResult.processed()

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
        "msg_batch_summary",
        msg=t("msg_success"),
        successful=2,
        skipped=0,
        failed=1,
        total=3,
    ), "[ui] Status label must display the formatted batch completion summary."
    assert "terminal_log" in ctx.summary_payload(), (
        "[ui] Batch summary payload must include captured terminal_log output."
    )
    assert_idle_ui(ctx)


def test_batch_with_skipped_files_logs_and_reports_counts(ctx):
    """Batch runs with skipped items emit [SKIP] log lines and report skipped count in status."""
    sample_path = ctx.in_dir / ctx.spec["in_name"]

    def fake_dir(**kwargs):
        cb = kwargs.get("progress_callback")
        if cb:
            cb(
                ProgressInfo(
                    current=1,
                    total=2,
                    file_path=sample_path,
                    start_time=0.0,
                    success=True,
                    skipped=True,
                    skip_reason_key="skip_not_smaller",
                    skip_reason_params={"quality": 80},
                )
            )
        print(f"[SKIP] {sample_path.name}")
        return {
            "success": 1,
            "skipped": 1,
            "failed": 0,
            "total_files": 2,
            "elapsed_seconds": 1.0,
            "original_bytes": 100,
            "compressed_bytes": 50,
            "cancelled": False,
            "cleaned_files_count": 0,
        }

    setattr(ctx.module, ctx.spec["dir_engine"], fake_dir)
    ctx.run_batch()

    ctx.summary_dialog.assert_called_once()
    payload = ctx.summary_payload()
    assert payload["skipped"] == 1, (
        "[ui] Batch summary payload must report skipped == 1."
    )
    assert "[SKIP]" in payload["terminal_log"], (
        "[ui] Batch terminal log must contain '[SKIP]' for skipped items."
    )
    assert ctx.lbl_status.value == t(
        "msg_batch_summary",
        msg=t("msg_success"),
        successful=1,
        skipped=1,
        failed=0,
        total=2,
    ), "[ui] Status label must include skipped count in msg_batch_summary."
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


def test_batch_returned_error_shows_error_without_success_dialog(ctx, caplog):
    """A returned batch-level error is logged and shown as an error, never as a success summary."""
    c = ctx
    c.fake_dir_engine(
        {
            "total_files": 3,
            "success": 0,
            "failed": 0,
            "elapsed_seconds": 0.0,
            "original_bytes": 0,
            "compressed_bytes": 0,
            "cancelled": False,
            "cleaned_files_count": 0,
            "error": "Cannot create output folder",
        }
    )
    streams_before = (sys.stdout, sys.stderr)

    with caplog.at_level(logging.ERROR):
        c.run_batch()

    assert "Cannot create output folder" in caplog.text, (
        "[ui] The returned batch error message must be logged."
    )
    assert c.lbl_status.value == t("msg_error"), (
        "[ui] A returned batch error must display the translated 'msg_error' status."
    )
    assert c.lbl_status.color == get_color("error"), (
        "[ui] A returned batch error must use the error color for the status label."
    )
    c.summary_dialog.assert_not_called()
    c.no_files_dialog.assert_not_called()
    assert c.progress_bar.value != 1.0, (
        "[ui] A batch error must not fill the progress bar as if the batch completed."
    )
    assert (sys.stdout, sys.stderr) == streams_before, (
        "[ui] Log redirection must be stopped even when the batch returns an error."
    )
    assert_idle_ui(c)


def test_batch_restores_standard_streams(ctx):
    """sys.stdout and sys.stderr are restored after the log redirector finishes."""
    before = (sys.stdout, sys.stderr)
    ctx.fake_dir_engine(BATCH_OK)
    ctx.run_batch()
    assert (sys.stdout, sys.stderr) == before, (
        "[ui] Batch execution must restore original sys.stdout and sys.stderr streams in finally block."
    )


def test_open_picker_blocks_concurrent_windows(ctx):
    """A second picker request is ignored while one native picker is still open."""
    picker = MagicMock()
    ctx.controller.open_picker(picker, allow_directory=True)
    ctx.controller.open_picker(picker, allow_directory=True)

    picker.get_directory_path.assert_called_once()
    assert ctx.controller.picker_active is True, (
        "[ui] Controller must hold picker_active=True while a native picker dialog is open."
    )


def test_open_picker_file_mode(ctx):
    """File mode opens the file picker with safe initial directory and allowed_extensions."""
    picker = MagicMock()
    ctx.controller.open_picker(
        picker, allow_directory=False, allowed_extensions=["mp4", "mkv"]
    )

    picker.pick_files.assert_called_once_with(
        allow_multiple=False,
        initial_directory=str(Path.home()),
        allowed_extensions=["mp4", "mkv"],
    )
    picker.get_directory_path.assert_not_called()


def test_handle_input_result_with_file(ctx):
    """Picking an input file stores it, releases the picker lock and updates the label."""
    lbl = MagicMock()
    event = MagicMock()
    event.files = [MagicMock(path=str(ctx.in_dir / "a.png"))]
    event.path = None
    ctx.controller.picker_active = True

    ctx.controller.handle_input_result(event, lbl, ctx.lbl_status)

    assert ctx.controller.selected_input == ctx.in_dir / "a.png", (
        "[ui] handle_input_result() must store the selected file Path on controller.selected_input."
    )
    assert ctx.controller.picker_active is False, (
        "[ui] handle_input_result() must release the picker_active concurrency lock."
    )
    assert lbl.value == "a.png", (
        "[ui] Input path label must display the selected filename."
    )
    assert ctx.lbl_status.value == "", (
        "[ui] Selecting a valid input file must clear any previous status message."
    )


def test_handle_input_result_with_directory(ctx):
    """Picking an input directory stores it and shows the directory name."""
    lbl = MagicMock()
    event = MagicMock()
    event.files = None
    event.path = str(ctx.in_dir)

    ctx.controller.handle_input_result(event, lbl)

    assert ctx.controller.selected_input == ctx.in_dir, (
        "[ui] handle_input_result() must store the selected folder Path on controller.selected_input."
    )
    assert lbl.value == ctx.in_dir.name, (
        "[ui] Input path label must display the selected directory name."
    )


def test_handle_input_result_cancelled_keeps_previous_selection(ctx):
    """Dismissing the input picker keeps the previous selection and releases the lock."""
    ctx.controller.selected_input = ctx.in_dir
    lbl = MagicMock()
    event = MagicMock()
    event.files = None
    event.path = None
    ctx.controller.picker_active = True

    ctx.controller.handle_input_result(event, lbl)

    assert ctx.controller.selected_input == ctx.in_dir, (
        "[ui] Cancelling the input picker must preserve the previously selected input path."
    )
    assert ctx.controller.picker_active is False, (
        "[ui] Cancelling the input picker must still release the picker_active lock."
    )


def test_handle_output_result(ctx):
    """Picking an output directory stores it, releases the picker lock and updates the label."""
    lbl = MagicMock()
    event = MagicMock()
    event.path = str(ctx.out_dir)
    ctx.controller.picker_active = True

    ctx.controller.handle_output_result(event, lbl, ctx.lbl_status)

    assert ctx.controller.selected_output_dir == ctx.out_dir, (
        "[ui] handle_output_result() must store the selected destination directory Path."
    )
    assert ctx.controller.picker_active is False, (
        "[ui] handle_output_result() must release the picker_active lock."
    )
    assert lbl.value == ctx.out_dir.name, (
        "[ui] Output path label must display the selected destination directory name."
    )


def test_handle_output_result_cancelled_keeps_state(ctx):
    """Dismissing the output picker selects nothing and releases the lock."""
    event = MagicMock()
    event.path = None
    ctx.controller.picker_active = True

    ctx.controller.handle_output_result(event, MagicMock())

    assert ctx.controller.selected_output_dir is None, (
        "[ui] Cancelling the output picker must leave selected_output_dir unchanged."
    )
    assert ctx.controller.picker_active is False, (
        "[ui] Cancelling the output picker must release the picker_active lock."
    )


def test_open_picker_uses_get_safe_initial_directory(ctx, monkeypatch):
    """Regression test ensuring open_picker uses get_safe_initial_directory to prevent OS picker crashes."""
    mock_get_safe = MagicMock(return_value=str(Path.home()))
    monkeypatch.setattr(
        "ui.controllers.base_controller.get_safe_initial_directory", mock_get_safe
    )

    picker = MagicMock()
    non_existent_path = ctx.in_dir / "deleted_folder"
    ctx.controller.selected_input = non_existent_path

    ctx.controller.open_picker(picker, allow_directory=True)

    mock_get_safe.assert_called_once_with(non_existent_path)
    picker.get_directory_path.assert_called_once_with(
        initial_directory=str(Path.home())
    )


def test_open_picker_fallback_to_home_on_deleted_directory(ctx):
    """Ensures file picker falls back to Home directory when previously selected directory was removed."""
    picker = MagicMock()
    deleted_dir = ctx.in_dir / "removed_dir"
    ctx.controller.selected_input = deleted_dir

    ctx.controller.open_picker(picker, allow_directory=False)

    picker.pick_files.assert_called_once_with(
        allow_multiple=False,
        initial_directory=str(Path.home()),
        allowed_extensions=None,
    )


def test_action_click_without_selection_asks_for_paths(ctx):
    """Starting without input/output selected asks the user to pick both and runs nothing."""
    ctx.execute()

    assert ctx.lbl_status.value == t("msg_select_required"), (
        "[ui] Attempting execution without input/output paths must display 'msg_select_required'."
    )
    assert ctx.controller.is_processing is False, (
        "[ui] Controller must not enter processing state when paths are missing."
    )
    ctx.summary_dialog.assert_not_called()


def test_action_click_same_folder_blocks_execution(ctx):
    """Starting with identical input and output directories blocks processing and shows error."""
    ctx.controller.selected_input = ctx.in_dir
    ctx.controller.selected_output_dir = ctx.in_dir

    ctx.execute()

    assert ctx.lbl_status.value == t("msg_same_folder_error"), (
        "[ui] Identical input and output directories must be blocked with 'msg_same_folder_error'."
    )
    assert ctx.controller.is_processing is False, (
        "[ui] Controller must remain idle when input and output directories are identical."
    )
    ctx.summary_dialog.assert_not_called()


def test_action_click_nested_folder_blocks_execution(ctx):
    """Starting with output directory nested within input directory blocks execution."""
    nested_dir = ctx.in_dir / "subfolder"
    nested_dir.mkdir(parents=True, exist_ok=True)
    ctx.controller.selected_input = ctx.in_dir
    ctx.controller.selected_output_dir = nested_dir

    ctx.execute()

    assert ctx.lbl_status.value == t("msg_nested_folder_error"), (
        "[ui] Output directory nested inside input directory must be blocked with 'msg_nested_folder_error'."
    )
    assert ctx.controller.is_processing is False, (
        "[ui] Controller must remain idle when output directory is nested inside input."
    )
    ctx.summary_dialog.assert_not_called()


def test_action_click_while_processing_opens_cancel_dialog(ctx):
    """Clicking the action button while processing routes to the cancel confirmation."""
    ctx.controller.is_processing = True
    ctx.controller._confirm_cancel_process = MagicMock()

    ctx.execute()

    ctx.controller._confirm_cancel_process.assert_called_once()


def test_cancel_dialog_confirm_sets_abort_flags(ctx):
    """Confirming the cancel dialog raises the abort flags (and the cancel event for video/image)."""
    ctx.controller.is_processing = True
    ctx.controller._confirm_cancel_process(
        ctx.page, ctx.lbl_status, ctx.progress_bar, ctx.btn_action
    )
    dialog = ctx.controller.cancel_dialog
    assert dialog is not None and dialog.open is True, (
        "[ui] _confirm_cancel_process() must open the confirmation AlertDialog."
    )

    stop_btn = dialog.actions[1]
    assert stop_btn.bgcolor == get_color("danger"), (
        "[ui] Confirm-stop button in cancel dialog must use 'danger' background color."
    )
    assert stop_btn.color == "#FFFFFF", (
        "[ui] Confirm-stop button text in cancel dialog must be '#FFFFFF'."
    )

    stop_btn.on_click(MagicMock())  # "Yes, stop and delete"

    assert ctx.controller.abort_requested is True, (
        "[ui] Confirming cancellation must set controller.abort_requested = True."
    )
    assert ctx.lbl_status.value == t("msg_cancelling"), (
        "[ui] Confirming cancellation must immediately update status label to 'msg_cancelling'."
    )
    assert dialog.open is False, (
        "[ui] Confirming cancellation must close the confirmation dialog."
    )
    assert ctx.controller.cancel_dialog is None, (
        "[ui] Controller must clear cancel_dialog reference after confirmation."
    )
    if ctx.spec["has_cancel_event"]:
        assert ctx.controller.cancel_event.is_set(), (
            "[ui] Confirming cancellation must signal controller.cancel_event so running workers abort."
        )


def test_cancel_dialog_keep_running_changes_nothing(ctx):
    """Dismissing the cancel dialog with 'keep running' leaves the job untouched."""
    ctx.controller.is_processing = True
    ctx.controller._confirm_cancel_process(
        ctx.page, ctx.lbl_status, ctx.progress_bar, ctx.btn_action
    )
    dialog = ctx.controller.cancel_dialog

    dialog.actions[0].on_click(MagicMock())  # "No, keep running"

    assert ctx.controller.abort_requested is False, (
        "[ui] Dismissing cancel dialog with 'keep running' must leave abort_requested as False."
    )
    assert dialog.open is False, (
        "[ui] Dismissing cancel dialog with 'keep running' must close the dialog."
    )
    if ctx.spec["has_cancel_event"]:
        assert not ctx.controller.cancel_event.is_set(), (
            "[ui] Dismissing cancel dialog with 'keep running' must not trigger cancel_event."
        )


def test_cancel_dialog_uses_correct_i18n_body_key(ctx):
    """Verifies that the cancellation dialog body uses the translated string from t('dialog_cancel_body')."""
    ctx.controller.is_processing = True
    ctx.controller._confirm_cancel_process(
        ctx.page, ctx.lbl_status, ctx.progress_bar, ctx.btn_action
    )
    dialog = ctx.controller.cancel_dialog
    assert dialog is not None, (
        "[ui] Cancellation dialog must be instantiated on _confirm_cancel_process()."
    )
    assert isinstance(dialog.content, ft.Text), (
        "[ui] Cancellation dialog content must be an ft.Text control."
    )
    assert dialog.content.value == t("dialog_cancel_body"), (
        "[ui] Cancellation dialog body must render translated t('dialog_cancel_body')."
    )
    assert dialog.content.value != "dialog_cancel_content", (
        "[ui] Cancellation dialog must not regress to the obsolete 'dialog_cancel_content' key."
    )


def test_image_cancellation_path_end_to_end(ctx):
    """Tests image cancellation path end-to-end when progress callback triggers cancellation."""
    ctx.controller.selected_input = ctx.in_dir
    ctx.controller.selected_output_dir = ctx.out_dir
    (ctx.in_dir / ctx.spec["in_name"]).write_bytes(b"data")

    def fake_dir_engine_interrupted(**kwargs):
        if hasattr(ctx.controller, "cancel_event"):
            ctx.controller.cancel_event.set()
        ctx.controller.abort_requested = True
        callback = kwargs.get("progress_callback")
        if callback:
            info = MagicMock()
            info.total = 1
            info.current = 1
            info.file_path = ctx.in_dir / ctx.spec["in_name"]
            info.success = True
            try:
                callback(info)
            except InterruptedError:
                pass
        return {"cancelled": True, "cleaned_files_count": 1}

    setattr(ctx.module, ctx.spec["dir_engine"], fake_dir_engine_interrupted)

    ctx.run_batch()

    assert ctx.lbl_status.value == t("msg_process_cancelled", count=1), (
        "[ui] End-to-end mid-batch cancellation must display 'msg_process_cancelled' with cleaned file count."
    )
    assert_idle_ui(ctx)


EXPECTED_SINGLE_FILE_NAME = {
    "image-compression": "photo_compressed.png",
    "image-conversion": "photo_converted.webp",
    "image-resize": "photo_resized.png",
    "image-metadata": "photo_clean.png",
    "video-compression": "clip_compressed.mp4",
    "video-conversion": "clip_converted.mp4",
    "audio-compression": "track_compressed.mp3",
    "audio-conversion": "track_converted.opus",
    "audio-extraction": "clip_extracted.mp3",
}


def test_single_file_output_name_uses_operation_suffix(ctx):
    """Single-file jobs name their output with the operation suffix."""
    if not ctx.spec.get("supports_single", True):
        pytest.skip(f"{ctx.spec['id']} is directory-only.")

    src = ctx.in_dir / ctx.spec["in_name"]
    out = ctx.controller.build_output_path(src, ctx.out_dir, ctx.params)

    assert out == ctx.out_dir / EXPECTED_SINGLE_FILE_NAME[ctx.spec["id"]], (
        f"[ui] '{ctx.spec['id']}' single-file output must be "
        f"'{EXPECTED_SINGLE_FILE_NAME[ctx.spec['id']]}', got '{out.name}'."
    )


def test_video_downscale_single_file_name_uses_height_suffix(tmp_path):
    """Downscale appends the resolved height and keeps the original container."""
    from ui.controllers.video_downscale_controller import VideoDownscaleController

    out = VideoDownscaleController().build_output_path(
        tmp_path / "clip.MKV", tmp_path / "out", "720p"
    )

    assert out == tmp_path / "out" / "clip_720p.mkv", (
        f"[ui] Downscale single-file output must be 'clip_720p.mkv', got '{out.name}'."
    )


def test_video_tracks_single_file_name_uses_tracks_suffix(tmp_path):
    """Track selection appends '_tracks' and keeps the original container."""
    from ui.controllers.video_tracks_controller import VideoTracksController

    out = VideoTracksController().build_output_path(
        tmp_path / "movie.MKV", tmp_path / "out", []
    )

    assert out == tmp_path / "out" / "movie_tracks.mkv", (
        f"[ui] Tracks single-file output must be 'movie_tracks.mkv', got '{out.name}'."
    )
