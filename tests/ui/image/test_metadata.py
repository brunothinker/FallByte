"""UI (image): metadata tests (controller and feature page)."""

from unittest.mock import MagicMock, patch

import flet as ft

from src.utils.file_result import FileResult
from tests.ui.helpers import make_job_ui
from ui.controllers.image_metadata_controller import ImageMetadataController


def test_image_metadata_batch_no_supported_files(tmp_workspace, mock_page):
    """Verifies image metadata controller handles empty/unsupported batch directories gracefully."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "notes.txt").write_bytes(b"text data")

    controller = ImageMetadataController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    ui = make_job_ui(mock_page)

    with (
        patch("ui.controllers.base_controller.show_summary_dialog") as mock_summary,
        patch(
            "ui.controllers.base_controller.show_no_supported_files_dialog"
        ) as mock_no_files,
    ):
        controller._run_batch_directory_job(ui, None)

        mock_summary.assert_not_called()
        mock_no_files.assert_called_once()
        assert "PNG" in mock_no_files.call_args.args[1], (
            "[ui] Image metadata unsupported-files dialog must advertise supported image formats such as 'PNG'."
        )
        assert ui.progress_bar.visible is False


def test_single_file_metadata_uses_unique_suffix_on_collision(
    tmp_workspace, mock_page, monkeypatch
):
    """Verifies single-file metadata removal avoids overwriting pre-existing destination files."""
    in_dir, out_dir = tmp_workspace
    src_file = in_dir / "portrait.jpg"
    src_file.write_bytes(b"source data")

    preexisting_file = out_dir / "portrait_clean.jpg"
    preexisting_file.write_bytes(b"existing clean content")

    controller = ImageMetadataController()
    controller.selected_input = src_file
    controller.selected_output_dir = out_dir

    ui = make_job_ui(mock_page)

    monkeypatch.setattr(
        "ui.controllers.base_controller.show_summary_dialog", MagicMock()
    )

    def fake_metadata_remover(input_path, output_path):
        output_path.write_bytes(b"new clean data")
        return FileResult.processed()

    monkeypatch.setattr(
        "ui.controllers.image_metadata_controller.file_metadata_remover",
        fake_metadata_remover,
    )

    controller._run_single_file_job(ui, None)

    assert preexisting_file.read_bytes() == b"existing clean content"
    expected_new = out_dir / "portrait_clean_2.jpg"
    assert expected_new.exists()
    assert expected_new.read_bytes() == b"new clean data"


def test_image_metadata_page_renders_and_registers_pickers(mock_page):
    """Verifies that image metadata removal page builds without error and registers FilePickers."""
    from ui.pages.image_metadata_page import create_image_metadata_page

    metadata_view = create_image_metadata_page(mock_page, {}, lambda _: None)
    assert isinstance(metadata_view, ft.Container), (
        "[ui] create_image_metadata_page() must return an ft.Container root view."
    )
    assert len(mock_page.overlay) == 0, (
        "[ui] Image metadata page must not pollute page.overlay in Flet 0.8+."
    )
