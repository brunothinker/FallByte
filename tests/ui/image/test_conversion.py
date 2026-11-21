"""UI (image): testes de conversion (controller + page da funcionalidade)."""

from unittest.mock import MagicMock, patch

import flet as ft

from ui.controllers.image_conversion_controller import ConversionController


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
