"""UI: BaseController path validation (#109), FilePicker registration, and cancellation."""

from pathlib import Path

import flet as ft

from ui.controllers.base_controller import _ensure_picker_registered
from ui.controllers.image_compression_controller import CompressionController


def _make_controller(in_path: Path | None, out_dir: Path | None) -> CompressionController:
    ctrl = CompressionController()
    ctrl.selected_input = in_path
    ctrl.selected_output_dir = out_dir
    return ctrl


def test_validate_paths_allows_same_or_parent_folder_for_single_file(tmp_path):
    """Single-file mode allows saving in the same or ancestor folder (#109)."""
    parent_dir = tmp_path / "photos"
    parent_dir.mkdir()
    img = parent_dir / "photo.png"
    img.write_bytes(b"png")

    ctrl_same = _make_controller(img, parent_dir)
    assert ctrl_same.validate_paths() is None

    ctrl_ancestor = _make_controller(img, tmp_path)
    assert ctrl_ancestor.validate_paths() is None


def test_validate_paths_blocks_same_or_nested_folder_for_directory(tmp_path):
    """Batch directory mode still blocks same or nested destination folders."""
    in_dir = tmp_path / "batch_in"
    nested_out = in_dir / "sub_out"
    in_dir.mkdir()
    nested_out.mkdir()

    ctrl_same = _make_controller(in_dir, in_dir)
    assert ctrl_same.validate_paths() is not None

    ctrl_nested = _make_controller(in_dir, nested_out)
    assert ctrl_nested.validate_paths() is not None


def test_ensure_picker_registered_adds_to_services_without_duplicates(mock_page):
    """_ensure_picker_registered registers a FilePicker in page.services only once."""
    mock_page.services = []
    picker = ft.FilePicker()

    _ensure_picker_registered(mock_page, picker)
    _ensure_picker_registered(mock_page, picker)

    assert mock_page.services == [picker]


def test_trigger_cancel_sets_abort_flag_and_event():
    """trigger_cancel sets abort_requested and signals cancel_event."""
    ctrl = CompressionController()
    assert ctrl.abort_requested is False
    assert ctrl.cancel_event.is_set() is False

    ctrl.trigger_cancel()

    assert ctrl.abort_requested is True
    assert ctrl.cancel_event.is_set() is True


def test_cancel_dialog_confirm_signals_cancel_event():
    """Confirming cancel dialog signals cancel_event via _on_cancel_confirmed."""
    ctrl = CompressionController()
    assert ctrl.cancel_event.is_set() is False

    ctrl._on_cancel_confirmed()

    assert ctrl.cancel_event.is_set() is True
