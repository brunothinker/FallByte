"""Integration tests for audio controller preflight checks (unsupported/uncompressible inputs, invalid selections)."""

from unittest.mock import MagicMock, patch

import flet as ft

from ui.controllers.audio_compression_controller import AudioCompressionController
from ui.controllers.audio_conversion_controller import AudioConversionController
from ui.controllers.audio_extraction_controller import AudioExtractionController
from ui.controllers.audio_normalization_controller import AudioNormalizationController


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


def test_audio_conversion_batch_no_supported_files(tmp_workspace, mock_page):
    """Verifies audio conversion controller handles empty/unsupported batch directories gracefully."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "notes.txt").write_bytes(b"text data")

    controller = AudioConversionController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    with (
        patch(
            "ui.controllers.audio_conversion_controller.show_summary_dialog"
        ) as mock_summary,
        patch(
            "ui.controllers.audio_conversion_controller.show_no_supported_files_dialog"
        ) as mock_no_files,
    ):
        controller._execute_batch_directory(
            page=mock_page,
            target_format="mp3",
            lbl_status=lbl_status,
            progress_bar=progress_bar,
            btn_action=btn_action,
        )

        mock_summary.assert_not_called()
        mock_no_files.assert_called_once()
        assert "FLAC" in mock_no_files.call_args.args[1], (
            "[ui] Audio conversion unsupported-files dialog must advertise all readable formats including 'FLAC'."
        )
        assert progress_bar.visible is False, (
            "[ui] Progress bar must remain hidden when audio conversion finds no supported files."
        )


def test_audio_extraction_batch_no_supported_files(tmp_workspace, mock_page):
    """Verifies audio extraction controller handles empty/unsupported batch directories gracefully."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "notes.txt").write_bytes(b"text data")

    controller = AudioExtractionController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    with (
        patch(
            "ui.controllers.audio_extraction_controller.show_summary_dialog"
        ) as mock_summary,
        patch(
            "ui.controllers.audio_extraction_controller.show_no_supported_files_dialog"
        ) as mock_no_files,
    ):
        controller._execute_batch_directory(
            page=mock_page,
            target_format="mp3",
            lbl_status=lbl_status,
            progress_bar=progress_bar,
            btn_action=btn_action,
        )

        mock_summary.assert_not_called()
        mock_no_files.assert_called_once()
        assert "MP4" in mock_no_files.call_args.args[1], (
            "[ui] Audio extraction unsupported-files dialog must advertise supported video formats including 'MP4'."
        )
        assert progress_bar.visible is False, (
            "[ui] Progress bar must remain hidden when audio extraction finds no supported videos."
        )


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

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    controller.execute_normalization(
        page=mock_page,
        preset_key="music",
        lbl_status=lbl_status,
        progress_bar=progress_bar,
        btn_action=btn_action,
    )
    assert controller.is_processing is False, (
        "[ui] Audio normalization must refuse single-file inputs since it is a directory-only workflow."
    )

    single_file.unlink()
    (in_dir / "notes.txt").write_bytes(b"text data")
    controller.selected_input = in_dir

    with (
        patch(
            "ui.controllers.audio_normalization_controller.show_summary_dialog"
        ) as mock_summary,
        patch(
            "ui.controllers.audio_normalization_controller.show_no_supported_files_dialog"
        ) as mock_no_files,
    ):
        controller._execute_batch_directory(
            page=mock_page,
            preset_key="podcast",
            lbl_status=lbl_status,
            progress_bar=progress_bar,
            btn_action=btn_action,
        )

        mock_summary.assert_not_called()
        mock_no_files.assert_called_once()
        assert "MP3" in mock_no_files.call_args.args[1], (
            "[ui] Audio normalization unsupported-files dialog must advertise supported formats including 'MP3'."
        )
        assert progress_bar.visible is False, (
            "[ui] Progress bar must remain hidden when audio normalization finds no supported files."
        )
