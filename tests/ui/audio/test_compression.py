"""UI (audio): testes de compression (controller + page da funcionalidade)."""

from unittest.mock import MagicMock, patch

from tests.ui.helpers import make_job_ui
from ui.controllers.audio_compression_controller import AudioCompressionController


def test_audio_compression_preflight_blocks_uncompressible_only_directory(
    tmp_workspace, mock_page
):
    """Preflight must stop early when directory contains only lossless/uncompressible audio files."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "master.wav").write_bytes(b"wav data")
    (in_dir / "archive.flac").write_bytes(b"flac data")

    controller = AudioCompressionController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    ui = make_job_ui(mock_page)

    proceed = MagicMock()

    with patch(
        "ui.controllers.base_controller.show_no_supported_files_dialog"
    ) as mock_no_files:
        controller.preflight_batch(ui, 80, proceed)

        mock_no_files.assert_called_once()
        formats = mock_no_files.call_args.args[1]
        assert "MP3" in formats and "OPUS" in formats, (
            "[ui] Audio compression preflight dialog must list compressible lossy formats ('MP3', 'OPUS')."
        )
        assert "WAV" not in formats and "FLAC" not in formats, (
            "[ui] Audio compression preflight dialog must exclude lossless formats ('WAV', 'FLAC')."
        )
        proceed.assert_not_called()


def test_audio_compression_preflight_warns_when_uncompressible_mixed_with_lossy(
    tmp_workspace, mock_page
):
    """Preflight must display incompatible-files warning when WAV/FLAC is mixed with MP3."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "song.mp3").write_bytes(b"mp3 data")
    (in_dir / "lossless.wav").write_bytes(b"wav data")

    controller = AudioCompressionController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    ui = make_job_ui(mock_page)

    proceed = MagicMock()

    controller.preflight_batch(ui, 80, proceed)

    assert mock_page.dialog is not None and mock_page.dialog.open is True, (
        "[ui] Mixing uncompressible WAV with compressible MP3 must open a confirmation warning dialog."
    )
    proceed.assert_not_called()
