"""Integration tests combining UI controllers with real engines, preflight checks, and file safety."""

from unittest.mock import MagicMock, patch

import flet as ft

from ui.controllers.audio_compression_controller import AudioCompressionController
from ui.controllers.audio_conversion_controller import AudioConversionController
from ui.controllers.audio_extraction_controller import AudioExtractionController
from ui.controllers.audio_normalization_controller import AudioNormalizationController
from ui.controllers.image_compression_controller import CompressionController
from ui.controllers.image_conversion_controller import ConversionController
from ui.controllers.image_metadata_controller import ImageMetadataController
from ui.controllers.image_resize_controller import (
    ImageResizeController,
    ResizeOptions,
)
from ui.controllers.video_compression_controller import VideoCompressionController
from ui.controllers.video_conversion_controller import VideoConversionController
from ui.i18n import t


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


def test_image_compression_batch_no_supported_files(tmp_workspace, mock_page):
    """Verifies image compression controller handles empty/unsupported batch directories gracefully."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "text.txt").write_bytes(b"text data")

    controller = CompressionController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    with (
        patch(
            "ui.controllers.image_compression_controller.show_summary_dialog"
        ) as mock_summary,
        patch(
            "ui.controllers.image_compression_controller.show_no_supported_files_dialog"
        ) as mock_no_files,
    ):
        controller._run_batch_compression(
            page=mock_page,
            quality=80,
            lbl_status=lbl_status,
            progress_bar=progress_bar,
            btn_action=btn_action,
        )

        mock_summary.assert_not_called()
        mock_no_files.assert_called_once()
        assert "JPG" in mock_no_files.call_args.args[1], (
            "[ui] Image compression unsupported-files dialog must advertise supported image formats such as 'JPG'."
        )
        assert progress_bar.visible is False, (
            "[ui] Progress bar must remain hidden when batch directory has no supported images."
        )


def test_image_conversion_batch_no_supported_files(tmp_workspace, mock_page):
    """Verifies image conversion controller handles empty/unsupported batch directories gracefully."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "text.txt").write_bytes(b"text data")

    controller = ConversionController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    with (
        patch(
            "ui.controllers.image_conversion_controller.show_summary_dialog"
        ) as mock_summary,
        patch(
            "ui.controllers.image_conversion_controller.show_no_supported_files_dialog"
        ) as mock_no_files,
    ):
        controller._execute_batch_directory(
            page=mock_page,
            target_format="webp",
            selected_color_key="transparent",
            lbl_status=lbl_status,
            progress_bar=progress_bar,
            btn_action=btn_action,
        )

        mock_summary.assert_not_called()
        mock_no_files.assert_called_once()
        assert "BMP" in mock_no_files.call_args.args[1], (
            "[ui] Image conversion unsupported-files dialog must list all readable input formats including 'BMP'."
        )
        assert progress_bar.visible is False, (
            "[ui] Progress bar must remain hidden when image conversion finds no supported files."
        )


def test_video_conversion_batch_no_supported_files(tmp_workspace, mock_page):
    """Verifies video conversion controller handles empty/unsupported batch directories gracefully."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "text.txt").write_bytes(b"text data")

    controller = VideoConversionController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    with (
        patch(
            "ui.controllers.video_conversion_controller.show_summary_dialog"
        ) as mock_summary,
        patch(
            "ui.controllers.video_conversion_controller.show_no_supported_files_dialog"
        ) as mock_no_files,
    ):
        controller._execute_batch_directory(
            page=mock_page,
            target_format="mp4",
            lbl_status=lbl_status,
            progress_bar=progress_bar,
            btn_action=btn_action,
        )

        mock_summary.assert_not_called()
        mock_no_files.assert_called_once()
        assert "MKV" in mock_no_files.call_args.args[1], (
            "[ui] Video conversion unsupported-files dialog must list supported containers including 'MKV'."
        )
        assert progress_bar.visible is False, (
            "[ui] Progress bar must remain hidden when video conversion finds no supported files."
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


def test_image_resize_validates_invalid_dimensions_and_percentage(
    tmp_workspace, mock_page
):
    """Ensures ImageResizeController rejects non-positive dimensions and out-of-range percentages."""
    in_dir, out_dir = tmp_workspace
    src_file = in_dir / "photo.png"
    src_file.write_bytes(b"png data")

    controller = ImageResizeController()
    controller.selected_input = src_file
    controller.selected_output_dir = out_dir

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    controller.execute_resize(
        page=mock_page,
        options=ResizeOptions(
            mode="dimension", max_width=None, max_height=0, percentage=None
        ),
        lbl_status=lbl_status,
        progress_bar=progress_bar,
        btn_action=btn_action,
    )
    assert lbl_status.value == t("msg_invalid_resize_dimensions"), (
        "[ui] Invalid resize dimensions must display 'msg_invalid_resize_dimensions'."
    )
    assert controller.is_processing is False

    controller.execute_resize(
        page=mock_page,
        options=ResizeOptions(
            mode="percentage", max_width=None, max_height=None, percentage=150
        ),
        lbl_status=lbl_status,
        progress_bar=progress_bar,
        btn_action=btn_action,
    )
    assert lbl_status.value == t("msg_invalid_resize_percentage"), (
        "[ui] Percentage above 100 must display 'msg_invalid_resize_percentage'."
    )
    assert controller.is_processing is False


def test_image_resize_batch_no_supported_files(tmp_workspace, mock_page):
    """Verifies image resize controller handles empty/unsupported batch directories gracefully."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "notes.txt").write_bytes(b"text data")

    controller = ImageResizeController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    with (
        patch(
            "ui.controllers.image_resize_controller.show_summary_dialog"
        ) as mock_summary,
        patch(
            "ui.controllers.image_resize_controller.show_no_supported_files_dialog"
        ) as mock_no_files,
    ):
        controller._execute_batch_directory(
            page=mock_page,
            options=ResizeOptions(
                mode="dimension", max_width=800, max_height=600, percentage=None
            ),
            lbl_status=lbl_status,
            progress_bar=progress_bar,
            btn_action=btn_action,
        )

        mock_summary.assert_not_called()
        mock_no_files.assert_called_once()
        assert "PNG" in mock_no_files.call_args.args[1], (
            "[ui] Image resize unsupported-files dialog must advertise supported image formats such as 'PNG'."
        )
        assert progress_bar.visible is False


def test_single_file_resize_uses_unique_suffix_on_collision(
    tmp_workspace, mock_page, monkeypatch
):
    """Verifies single-file resize avoids overwriting pre-existing destination files."""
    in_dir, out_dir = tmp_workspace
    src_file = in_dir / "banner.png"
    src_file.write_bytes(b"source data")

    preexisting_file = out_dir / "banner_resized.png"
    preexisting_file.write_bytes(b"existing resized content")

    controller = ImageResizeController()
    controller.selected_input = src_file
    controller.selected_output_dir = out_dir

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    monkeypatch.setattr(
        "ui.controllers.image_resize_controller.show_summary_dialog", MagicMock()
    )
    monkeypatch.setattr(
        "ui.controllers.image_resize_controller.file_resizer",
        lambda input_path, output_path, **kwargs: (
            output_path.write_bytes(b"new resized data") or True
        ),
    )

    controller._execute_single_file(
        page=mock_page,
        options=ResizeOptions(
            mode="percentage", max_width=None, max_height=None, percentage=50
        ),
        lbl_status=lbl_status,
        progress_bar=progress_bar,
        btn_action=btn_action,
    )

    assert preexisting_file.read_bytes() == b"existing resized content"
    expected_new = out_dir / "banner_resized_2.png"
    assert expected_new.exists()
    assert expected_new.read_bytes() == b"new resized data"


def test_image_metadata_batch_no_supported_files(tmp_workspace, mock_page):
    """Verifies image metadata controller handles empty/unsupported batch directories gracefully."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "notes.txt").write_bytes(b"text data")

    controller = ImageMetadataController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    with (
        patch(
            "ui.controllers.image_metadata_controller.show_summary_dialog"
        ) as mock_summary,
        patch(
            "ui.controllers.image_metadata_controller.show_no_supported_files_dialog"
        ) as mock_no_files,
    ):
        controller._execute_batch_directory(
            page=mock_page,
            lbl_status=lbl_status,
            progress_bar=progress_bar,
            btn_action=btn_action,
        )

        mock_summary.assert_not_called()
        mock_no_files.assert_called_once()
        assert "PNG" in mock_no_files.call_args.args[1], (
            "[ui] Image metadata unsupported-files dialog must advertise supported image formats such as 'PNG'."
        )
        assert progress_bar.visible is False


def test_single_file_metadata_uses_unique_suffix_on_collision(
    tmp_workspace, mock_page, monkeypatch
):
    """Verifies single-file metadata removal avoids overwriting pre-existing destination files."""
    in_dir, out_dir = tmp_workspace
    src_file = in_dir / "portrait.jpg"
    src_file.write_bytes(b"source data")

    preexisting_file = out_dir / "portrait_clean.jpg"
    preexisting_file.write_bytes(b"existing clean content")

    controller = ImageMetadataController()
    controller.selected_input = src_file
    controller.selected_output_dir = out_dir

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    monkeypatch.setattr(
        "ui.controllers.image_metadata_controller.show_summary_dialog", MagicMock()
    )
    monkeypatch.setattr(
        "ui.controllers.image_metadata_controller.file_metadata_remover",
        lambda input_path, output_path: (
            output_path.write_bytes(b"new clean data") or True
        ),
    )

    controller._execute_single_file(
        page=mock_page,
        lbl_status=lbl_status,
        progress_bar=progress_bar,
        btn_action=btn_action,
    )

    assert preexisting_file.read_bytes() == b"existing clean content"
    expected_new = out_dir / "portrait_clean_2.jpg"
    assert expected_new.exists()
    assert expected_new.read_bytes() == b"new clean data"
