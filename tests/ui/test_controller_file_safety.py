"""Integration tests for controller file safety: failure logging, navigation locks, overwrite and cancellation guarantees."""

from unittest.mock import MagicMock, patch

import flet as ft

from ui.controllers.image_compression_controller import CompressionController
from ui.controllers.video_compression_controller import VideoCompressionController


def test_ui_log_reflects_failed_compression(tmp_workspace, mock_page):
    """Tests controller and UI integration ensuring batch processing failures write '[FAIL]' logs instead of false positives."""
    in_dir, out_dir = tmp_workspace

    corrupted_file = in_dir / "bad_image.png"
    corrupted_file.write_bytes(b"NOT_A_VALID_IMAGE_HEADER")

    controller = CompressionController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    with patch(
        "ui.controllers.image_compression_controller.show_summary_dialog"
    ) as mock_show_dialog:
        controller._run_batch_compression(
            page=mock_page,
            quality=80,
            lbl_status=lbl_status,
            progress_bar=progress_bar,
            btn_action=btn_action,
        )

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

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    monkeypatch.setattr(
        "ui.controllers.image_compression_controller.show_summary_dialog", MagicMock()
    )
    monkeypatch.setattr(
        "ui.controllers.image_compression_controller.file_compressor",
        lambda input_path, output_path, quality, strip_metadata=False: (
            output_path.write_bytes(b"compressed data") or True
        ),
    )

    controller._execute_single_file(
        page=mock_page,
        quality=80,
        lbl_status=lbl_status,
        progress_bar=progress_bar,
        btn_action=btn_action,
    )

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

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    captured_kwargs: dict[str, object] = {}

    def fake_compressor(input_path, output_path, quality, strip_metadata=False):
        captured_kwargs["strip_metadata"] = strip_metadata
        output_path.write_bytes(b"clean compressed")
        return True

    monkeypatch.setattr(
        "ui.controllers.image_compression_controller.show_summary_dialog", MagicMock()
    )
    monkeypatch.setattr(
        "ui.controllers.image_compression_controller.file_compressor",
        fake_compressor,
    )

    controller._execute_single_file(
        page=mock_page,
        quality=80,
        lbl_status=lbl_status,
        progress_bar=progress_bar,
        btn_action=btn_action,
        strip_metadata=True,
    )

    assert captured_kwargs.get("strip_metadata") is True


def test_single_file_compression_cancellation_preserves_preexisting_file(
    tmp_workspace, mock_page, monkeypatch
):
    """Verifies that cancelling single-file compression does not delete pre-existing user files in the destination."""
    in_dir, out_dir = tmp_workspace
    src_file = in_dir / "sample.mp4"
    src_file.write_bytes(b"source video")

    preexisting_file = out_dir / "sample_compressed.mp4"
    preexisting_file.write_bytes(b"preexisting user video")

    controller = VideoCompressionController()
    controller.selected_input = src_file
    controller.selected_output_dir = out_dir
    controller.abort_requested = True

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    monkeypatch.setattr(
        "ui.controllers.video_compression_controller.show_summary_dialog", MagicMock()
    )
    monkeypatch.setattr(
        "ui.controllers.video_compression_controller.file_compressor",
        lambda **kwargs: False,
    )

    controller._execute_single_file(
        page=mock_page,
        quality=80,
        lbl_status=lbl_status,
        progress_bar=progress_bar,
        btn_action=btn_action,
    )

    assert preexisting_file.exists(), (
        "[ui] Cancelling single-file compression must not unlink pre-existing user files in output_dir."
    )
    assert preexisting_file.read_bytes() == b"preexisting user video", (
        "[ui] Cancelling single-file compression must preserve pre-existing user file contents untouched."
    )
