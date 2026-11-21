"""UI (video): testes de compression (controller + page da funcionalidade)."""

from unittest.mock import MagicMock, patch

import flet as ft

from ui.controllers.video_compression_controller import VideoCompressionController


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


def test_video_compression_preflight_empty_supported_files(tmp_workspace, mock_page):
    """Verifies that preflight stops early when no supported video files exist in the batch directory."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "document.pdf").write_bytes(b"pdf data")

    controller = VideoCompressionController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    with (
        patch(
            "ui.controllers.video_compression_controller.show_no_supported_files_dialog"
        ) as mock_no_files,
        patch(
            "ui.controllers.video_compression_controller.threading.Thread"
        ) as mock_thread,
    ):
        controller._preflight_batch_execution(
            page=mock_page,
            quality=80,
            lbl_status=lbl_status,
            progress_bar=progress_bar,
            btn_action=btn_action,
        )

        mock_no_files.assert_called_once()
        formats = mock_no_files.call_args.args[1]
        assert "MP4" in formats and "PDF" not in formats, (
            "[ui] Video preflight unsupported-files dialog must list supported video formats ('MP4') and exclude 'PDF'."
        )
        mock_thread.assert_not_called()
