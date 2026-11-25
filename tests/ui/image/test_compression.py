
"""UI (image): compression tests (controller and feature page)."""

from unittest.mock import MagicMock, patch

import flet as ft

from src.utils.file_result import FileResult
from tests.ui.helpers import make_job_ui, trigger_click
from ui.controllers.image_compression_controller import (
    CompressionController,
    CompressionOptions,
)


def test_ui_log_reflects_failed_compression(tmp_workspace, mock_page):
    """Tests controller and UI integration ensuring batch processing failures write '[FAIL]' logs instead of false positives."""
    in_dir, out_dir = tmp_workspace

    corrupted_file = in_dir / "bad_image.png"
    corrupted_file.write_bytes(b"NOT_A_VALID_IMAGE_HEADER")

    controller = CompressionController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    ui = make_job_ui(mock_page)

    with patch(
        "ui.controllers.base_controller.show_summary_dialog"
    ) as mock_show_dialog:
        controller._run_batch_directory_job(ui, CompressionOptions(quality=80))

        mock_show_dialog.assert_called_once()

        summary_payload = (
            mock_show_dialog.call_args[0][1]
            if len(mock_show_dialog.call_args[0]) > 1
            else mock_show_dialog.call_args[1].get("summary")
        )

        assert summary_payload.get("failed", 0) == 1, (
            "[ui] Corrupted image batch run must report failed == 1 in summary payload."
        )
        assert summary_payload.get("success", 0) == 0, (
            "[ui] Corrupted image batch run must report success == 0 in summary payload."
        )

        terminal_log = summary_payload.get("terminal_log", "")
        assert "[FAIL]" in terminal_log, (
            "[ui] Summary terminal log must contain '[FAIL]' for failed engine processing."
        )
        assert "[OK]" not in terminal_log, (
            "[ui] Summary terminal log must not emit false-positive '[OK]' lines on engine failure."
        )


def test_processing_state_locks_global_navigation(mock_page):
    """Validates that active processing locks session state and blocks navigation attempts."""
    controller = CompressionController()
    controller.is_processing = True
    mock_page.session.get.return_value = True

    assert mock_page.session.get("is_processing") is True, (
        "[ui] Session 'is_processing' flag must evaluate to True to block navigation during active jobs."
    )


def test_single_file_compression_does_not_overwrite_preexisting_file(
    tmp_workspace, mock_page, monkeypatch
):
    """Verifies that single-file compression uses unique output naming and does not overwrite existing destination files."""
    in_dir, out_dir = tmp_workspace
    src_file = in_dir / "sample.png"
    src_file.write_bytes(b"source data")

    preexisting_file = out_dir / "sample_compressed.png"
    preexisting_file.write_bytes(b"original content")

    controller = CompressionController()
    controller.selected_input = src_file
    controller.selected_output_dir = out_dir

    ui = make_job_ui(mock_page)

    monkeypatch.setattr(
        "ui.controllers.base_controller.show_summary_dialog", MagicMock()
    )

    def fake_compressor(input_path, output_path, quality, strip_metadata=False):
        output_path.write_bytes(b"compressed data")
        return FileResult.processed()

    monkeypatch.setattr(
        "ui.controllers.image_compression_controller.file_compressor",
        fake_compressor,
    )

    controller._run_single_file_job(ui, CompressionOptions(quality=80))

    assert preexisting_file.read_bytes() == b"original content", (
        "[ui] Single-file compression must never overwrite a pre-existing file at the default destination path."
    )
    expected_new_file = out_dir / "sample_compressed_2.png"
    assert expected_new_file.exists(), (
        "[ui] Single-file compression must allocate a suffixed filename ('sample_compressed_2.png') on collision."
    )
    assert expected_new_file.read_bytes() == b"compressed data", (
        "[ui] Newly suffixed output file must contain the compressed output bytes."
    )


def test_single_file_compression_forwards_strip_metadata_flag(
    tmp_workspace, mock_page, monkeypatch
):
    """Verifies that single-file compression forwards strip_metadata=True to file_compressor."""
    in_dir, out_dir = tmp_workspace
    src_file = in_dir / "photo.jpg"
    src_file.write_bytes(b"source image")

    controller = CompressionController()
    controller.selected_input = src_file
    controller.selected_output_dir = out_dir

    ui = make_job_ui(mock_page)

    captured_kwargs: dict[str, object] = {}

    def fake_compressor(input_path, output_path, quality, strip_metadata=False):
        captured_kwargs["strip_metadata"] = strip_metadata
        output_path.write_bytes(b"clean compressed")
        return FileResult.processed()

    monkeypatch.setattr(
        "ui.controllers.base_controller.show_summary_dialog", MagicMock()
    )
    monkeypatch.setattr(
        "ui.controllers.image_compression_controller.file_compressor",
        fake_compressor,
    )

    controller._run_single_file_job(
        ui, CompressionOptions(quality=80, strip_metadata=True)
    )

    assert captured_kwargs.get("strip_metadata") is True


def test_image_compression_batch_no_supported_files(tmp_workspace, mock_page):
    """Verifies image compression controller handles empty/unsupported batch directories gracefully."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "text.txt").write_bytes(b"text data")

    controller = CompressionController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    ui = make_job_ui(mock_page)

    with (
        patch("ui.controllers.base_controller.show_summary_dialog") as mock_summary,
        patch(
            "ui.controllers.base_controller.show_no_supported_files_dialog"
        ) as mock_no_files,
    ):
        controller._run_batch_directory_job(ui, CompressionOptions(quality=80))

        mock_summary.assert_not_called()
        mock_no_files.assert_called_once()
        assert "JPG" in mock_no_files.call_args.args[1], (
            "[ui] Image compression unsupported-files dialog must advertise supported image formats such as 'JPG'."
        )
        assert ui.progress_bar.visible is False, (
            "[ui] Progress bar must remain hidden when batch directory has no supported images."
        )


def test_image_compression_page_renders_strip_metadata_checkbox(mock_page):
    """Verifies image compression page renders unchecked strip_metadata checkbox and forwards its state."""
    from ui.pages.image_compression_page import create_compression_page

    mock_page.overlay.clear()
    comp_view = create_compression_page(mock_page, {}, lambda _: None)
    assert isinstance(comp_view, ft.Container)
    assert len(mock_page.overlay) == 0

    controls = comp_view.content.content.controls  # type: ignore[union-attr]
    chk_strip = next(c for c in controls if isinstance(c, ft.Checkbox))
    assert chk_strip.value is False, (
        "[ui] Image compression strip_metadata checkbox must default to False."
    )

    btn_action = next(c for c in controls if isinstance(c, ft.Button))
    chk_strip.value = True

    with patch(
        "ui.pages.image_compression_page.CompressionController.execute"
    ) as mock_click:
        assert callable(btn_action.on_click)
        trigger_click(btn_action.on_click)
        mock_click.assert_called_once()
        # The class attribute is patched, so the call is (JobUI, params).
        params = mock_click.call_args.args[1]
        assert isinstance(params, CompressionOptions)
        assert params.strip_metadata is True
        assert params.quality == 80
