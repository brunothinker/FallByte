"""Characterization tests for controller path validation, action routing, and cancellation dialogs."""

from unittest.mock import MagicMock

import flet as ft

from tests.ui.helpers import assert_idle_ui
from ui.i18n import t
from ui.theme import get_color


def test_action_click_without_selection_asks_for_paths(ctx):
    """Starting without input/output selected asks the user to pick both and runs nothing."""
    getattr(ctx.controller, ctx.spec["entry"])(
        page=ctx.page, **ctx.spec["kwargs"], **ctx.widgets()
    )

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

    getattr(ctx.controller, ctx.spec["entry"])(
        page=ctx.page, **ctx.spec["kwargs"], **ctx.widgets()
    )

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

    getattr(ctx.controller, ctx.spec["entry"])(
        page=ctx.page, **ctx.spec["kwargs"], **ctx.widgets()
    )

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

    ctx.controller.handle_action_click(
        page=ctx.page, **ctx.spec["kwargs"], **ctx.widgets()
    )

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

    getattr(ctx.controller, ctx.spec["batch"])(
        page=ctx.page, **ctx.spec["kwargs"], **ctx.widgets()
    )

    assert ctx.lbl_status.value == t("msg_process_cancelled", count=1), (
        "[ui] End-to-end mid-batch cancellation must display 'msg_process_cancelled' with cleaned file count."
    )
    assert_idle_ui(ctx)