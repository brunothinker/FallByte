"""Integration tests for image and video controller preflight checks when no supported files are found."""

from unittest.mock import MagicMock, patch

import flet as ft

from ui.controllers.image_compression_controller import CompressionController
from ui.controllers.image_conversion_controller import ConversionController
from ui.controllers.video_compression_controller import VideoCompressionController
from ui.controllers.video_conversion_controller import VideoConversionController


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
