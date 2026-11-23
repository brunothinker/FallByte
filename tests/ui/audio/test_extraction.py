"""UI (audio): testes de extraction (controller + page da funcionalidade)."""

from unittest.mock import MagicMock, patch

from tests.ui.helpers import make_job_ui
from ui.controllers.audio_extraction_controller import AudioExtractionController


def test_audio_extraction_batch_no_supported_files(tmp_workspace, mock_page):
    """Verifies audio extraction controller handles empty/unsupported batch directories gracefully."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "notes.txt").write_bytes(b"text data")

    controller = AudioExtractionController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    ui = make_job_ui(mock_page)

    with (
        patch("ui.controllers.base_controller.show_summary_dialog") as mock_summary,
        patch(
            "ui.controllers.base_controller.show_no_supported_files_dialog"
        ) as mock_no_files,
    ):
        controller._run_batch_directory_job(ui, "mp3")

        mock_summary.assert_not_called()
        mock_no_files.assert_called_once()
        assert "MP4" in mock_no_files.call_args.args[1], (
            "[ui] Audio extraction unsupported-files dialog must advertise supported video formats including 'MP4'."
        )
        assert ui.progress_bar.visible is False, (
            "[ui] Progress bar must remain hidden when audio extraction finds no supported videos."
        )
