"""UI (audio): testes de normalization (controller + page da funcionalidade)."""

from unittest.mock import patch

from tests.ui.helpers import make_job_ui
from ui.controllers.audio_normalization_controller import AudioNormalizationController


def test_audio_normalization_rejects_single_file_and_handles_no_supported_files(
    tmp_workspace, mock_page
):
    """Verifies normalization rejects single-file input and handles unsupported batch directories gracefully."""
    in_dir, out_dir = tmp_workspace
    single_file = in_dir / "single.mp3"
    single_file.write_bytes(b"mp3 data")

    controller = AudioNormalizationController()
    controller.selected_input = single_file
    controller.selected_output_dir = out_dir

    ui = make_job_ui(mock_page)

    controller.execute(ui, "music")
    assert controller.is_processing is False, (
        "[ui] Audio normalization must refuse single-file inputs since it is a directory-only workflow."
    )

    single_file.unlink()
    (in_dir / "notes.txt").write_bytes(b"text data")
    controller.selected_input = in_dir

    with (
        patch("ui.controllers.base_controller.show_summary_dialog") as mock_summary,
        patch(
            "ui.controllers.base_controller.show_no_supported_files_dialog"
        ) as mock_no_files,
    ):
        controller._run_batch_directory_job(ui, "podcast")

        mock_summary.assert_not_called()
        mock_no_files.assert_called_once()
        assert "MP3" in mock_no_files.call_args.args[1], (
            "[ui] Audio normalization unsupported-files dialog must advertise supported formats including 'MP3'."
        )
        assert ui.progress_bar.visible is False, (
            "[ui] Progress bar must remain hidden when audio normalization finds no supported files."
        )
