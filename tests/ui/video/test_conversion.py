"""UI (video): testes de conversion (controller + page da funcionalidade)."""

from unittest.mock import MagicMock, patch

from tests.ui.helpers import make_job_ui
from ui.controllers.video_conversion_controller import VideoConversionController


def test_video_conversion_batch_no_supported_files(tmp_workspace, mock_page):
    """Verifies video conversion controller handles empty/unsupported batch directories gracefully."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "text.txt").write_bytes(b"text data")

    controller = VideoConversionController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    ui = make_job_ui(mock_page)

    with (
        patch("ui.controllers.base_controller.show_summary_dialog") as mock_summary,
        patch(
            "ui.controllers.base_controller.show_no_supported_files_dialog"
        ) as mock_no_files,
    ):
        controller._run_batch_directory_job(ui, "mp4")

        mock_summary.assert_not_called()
        mock_no_files.assert_called_once()
        assert "MKV" in mock_no_files.call_args.args[1], (
            "[ui] Video conversion unsupported-files dialog must list supported containers including 'MKV'."
        )
        assert ui.progress_bar.visible is False, (
            "[ui] Progress bar must remain hidden when video conversion finds no supported files."
        )
