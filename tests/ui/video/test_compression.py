"""UI (video): testes from compression (controller and feature page)."""

from unittest.mock import MagicMock, patch

from tests.ui.helpers import make_job_ui
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

    ui = make_job_ui(mock_page)

    def cancelled_engine(**kwargs):
        raise InterruptedError("CANCELLED_BY_USER")

    mock_summary = MagicMock()
    monkeypatch.setattr(
        "ui.controllers.base_controller.show_summary_dialog", mock_summary
    )
    monkeypatch.setattr(
        "ui.controllers.video_compression_controller.file_compressor",
        cancelled_engine,
    )

    controller._run_single_file_job(ui, 80)

    mock_summary.assert_not_called()

    assert preexisting_file.exists(), (
        "[ui] Cancelling single-file compression must not unlink pre-existing user files in output_dir."
    )
    assert preexisting_file.read_bytes() == b"preexisting user video", (
        "[ui] Cancelling single-file compression must preserve pre-existing user file contents untouched."
    )


def test_video_compression_batch_empty_supported_files(tmp_workspace, mock_page):
    """Verifies that batch job shows the no-supported-files dialog when no supported video files exist."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "document.pdf").write_bytes(b"pdf data")

    controller = VideoCompressionController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    ui = make_job_ui(mock_page)

    with (
        patch(
            "ui.controllers.video_compression_controller.directory_compressor",
            return_value={"no_files": True},
        ),
        patch(
            "ui.controllers.base_controller.show_no_supported_files_dialog"
        ) as mock_no_files,
        patch("ui.controllers.base_controller.show_summary_dialog") as mock_summary,
    ):
        controller._run_batch_directory_job(ui, 80)

        mock_no_files.assert_called_once()
        formats = mock_no_files.call_args.args[1]
        assert "MP4" in formats and "PDF" not in formats, (
            "[ui] Video batch no-files dialog must list supported video formats ('MP4') and exclude 'PDF'."
        )
        mock_summary.assert_not_called()
