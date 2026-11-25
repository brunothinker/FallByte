"""UI (image): resize tests (controller and feature page)."""

from unittest.mock import MagicMock, patch

import flet as ft

from src.utils.file_result import FileResult
from tests.ui.helpers import make_job_ui
from ui.controllers.image_resize_controller import ImageResizeController, ResizeOptions
from ui.i18n import t


def test_image_resize_validates_invalid_dimensions_and_percentage(
    tmp_workspace, mock_page
):
    """Ensures ImageResizeController rejects non-positive dimensions and out-of-range percentages."""
    in_dir, out_dir = tmp_workspace
    src_file = in_dir / "photo.png"
    src_file.write_bytes(b"png data")

    controller = ImageResizeController()
    controller.selected_input = src_file
    controller.selected_output_dir = out_dir

    ui = make_job_ui(mock_page)

    controller.execute(
        ui,
        ResizeOptions(mode="dimension", max_width=None, max_height=0, percentage=None),
    )
    assert ui.lbl_status.value == t("msg_invalid_resize_dimensions"), (
        "[ui] Invalid resize dimensions must display 'msg_invalid_resize_dimensions'."
    )
    assert controller.is_processing is False

    controller.execute(
        ui,
        ResizeOptions(
            mode="percentage", max_width=None, max_height=None, percentage=150
        ),
    )
    assert ui.lbl_status.value == t("msg_invalid_resize_percentage"), (
        "[ui] Percentage above 100 must display 'msg_invalid_resize_percentage'."
    )
    assert controller.is_processing is False


def test_image_resize_batch_no_supported_files(tmp_workspace, mock_page):
    """Verifies image resize controller handles empty/unsupported batch directories gracefully."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "notes.txt").write_bytes(b"text data")

    controller = ImageResizeController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    ui = make_job_ui(mock_page)

    with (
        patch("ui.controllers.base_controller.show_summary_dialog") as mock_summary,
        patch(
            "ui.controllers.base_controller.show_no_supported_files_dialog"
        ) as mock_no_files,
    ):
        controller._run_batch_directory_job(
            ui,
            ResizeOptions(
                mode="dimension", max_width=800, max_height=600, percentage=None
            ),
        )

        mock_summary.assert_not_called()
        mock_no_files.assert_called_once()
        assert "PNG" in mock_no_files.call_args.args[1], (
            "[ui] Image resize unsupported-files dialog must advertise supported image formats such as 'PNG'."
        )
        assert ui.progress_bar.visible is False


def test_single_file_resize_uses_unique_suffix_on_collision(
    tmp_workspace, mock_page, monkeypatch
):
    """Verifies single-file resize avoids overwriting pre-existing destination files."""
    in_dir, out_dir = tmp_workspace
    src_file = in_dir / "banner.png"
    src_file.write_bytes(b"source data")

    preexisting_file = out_dir / "banner_resized.png"
    preexisting_file.write_bytes(b"existing resized content")

    controller = ImageResizeController()
    controller.selected_input = src_file
    controller.selected_output_dir = out_dir

    ui = make_job_ui(mock_page)

    monkeypatch.setattr(
        "ui.controllers.base_controller.show_summary_dialog", MagicMock()
    )

    def fake_resizer(input_path, output_path, **kwargs):
        output_path.write_bytes(b"new resized data")
        return FileResult.processed()

    monkeypatch.setattr(
        "ui.controllers.image_resize_controller.file_resizer",
        fake_resizer,
    )

    controller._run_single_file_job(
        ui,
        ResizeOptions(
            mode="percentage", max_width=None, max_height=None, percentage=50
        ),
    )

    assert preexisting_file.read_bytes() == b"existing resized content"
    expected_new = out_dir / "banner_resized_2.png"
    assert expected_new.exists()
    assert expected_new.read_bytes() == b"new resized data"


def test_image_resize_page_renders_and_register_pickers(mock_page):
    """Verifies that image resize page builds without error, registers FilePickers, and exposes expected modes."""
    from ui.pages.image_resize_page import create_image_resize_page

    resize_view = create_image_resize_page(mock_page, {}, lambda _: None)
    assert isinstance(resize_view, ft.Container), (
        "[ui] create_image_resize_page() must return an ft.Container root view."
    )
    assert len(mock_page.overlay) == 0, (
        "[ui] Image resize page must not pollute page.overlay in Flet 0.8+."
    )

    resize_controls = resize_view.content.content.controls  # type: ignore[union-attr]
    mode_dropdown = next(c for c in resize_controls if isinstance(c, ft.Dropdown))
    assert [o.key for o in (mode_dropdown.options or [])] == [
        "dimension",
        "percentage",
    ], "[ui] Image resize page dropdown must expose ['dimension', 'percentage'] modes."
    assert mode_dropdown.value == "dimension", (
        "[ui] Image resize page dropdown must default to 'dimension' mode."
    )
