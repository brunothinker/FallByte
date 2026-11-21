"""UI (audio): testes de compression (controller + page da funcionalidade)."""

from unittest.mock import MagicMock, patch

import flet as ft

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

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    with (
        patch(
            "ui.controllers.audio_compression_controller.show_no_supported_files_dialog"
        ) as mock_no_files,
        patch(
            "ui.controllers.audio_compression_controller.threading.Thread"
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
        assert "MP3" in formats and "OPUS" in formats, (
            "[ui] Audio compression preflight dialog must list compressible lossy formats ('MP3', 'OPUS')."
        )
        assert "WAV" not in formats and "FLAC" not in formats, (
            "[ui] Audio compression preflight dialog must exclude lossless formats ('WAV', 'FLAC')."
        )
        mock_thread.assert_not_called()


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

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    with patch(
        "ui.controllers.audio_compression_controller.threading.Thread"
    ) as mock_thread:
        controller._preflight_batch_execution(
            page=mock_page,
            quality=80,
            lbl_status=lbl_status,
            progress_bar=progress_bar,
            btn_action=btn_action,
        )

        assert mock_page.dialog is not None and mock_page.dialog.open is True, (
            "[ui] Mixing uncompressible WAV with compressible MP3 must open a confirmation warning dialog."
        )
        mock_thread.assert_not_called()
