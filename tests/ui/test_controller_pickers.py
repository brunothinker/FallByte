"""Tests for file/folder picker concurrency locks, selection callbacks, and safe initial directories."""

from pathlib import Path
from unittest.mock import MagicMock


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
    monkeypatch.setattr("ui.controllers.base_controller.get_safe_initial_directory", mock_get_safe)

    picker = MagicMock()
    non_existent_path = ctx.in_dir / "deleted_folder"
    ctx.controller.selected_input = non_existent_path

    ctx.controller.open_picker(picker, allow_directory=True)

    mock_get_safe.assert_called_once_with(non_existent_path)
    picker.get_directory_path.assert_called_once_with(initial_directory=str(Path.home()))


def test_open_picker_fallback_to_home_on_deleted_directory(ctx):
    """Ensures file picker falls back to Home directory when previously selected directory was removed."""
    picker = MagicMock()
    deleted_dir = ctx.in_dir / "removed_dir"
    ctx.controller.selected_input = deleted_dir

    ctx.controller.open_picker(picker, allow_directory=False)

    picker.pick_files.assert_called_once_with(
        allow_multiple=False, initial_directory=str(Path.home()), allowed_extensions=None
    )