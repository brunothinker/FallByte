"""UI (audio): single-file extraction tests (controller and feature page)."""

from unittest.mock import patch

from tests.ui.helpers import make_job_ui
from ui.controllers.audio_extraction_controller import AudioExtractionController
from ui.i18n import t


def test_audio_extraction_rejects_directory_input(tmp_workspace, mock_page):
    """Verifies single-file audio extraction rejects directory selection with an error status."""
    in_dir, out_dir = tmp_workspace

    controller = AudioExtractionController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    ui = make_job_ui(mock_page)

    with (
        patch("ui.controllers.base_controller.show_summary_dialog") as mock_summary,
        patch.object(controller, "_start_thread") as mock_thread,
    ):
        controller.execute(ui, "mp3")

        mock_summary.assert_not_called()
        mock_thread.assert_not_called()
        assert ui.lbl_status.value == t("msg_single_video_required")
