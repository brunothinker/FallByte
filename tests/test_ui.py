from unittest.mock import MagicMock, patch

import flet as ft

from ui.controllers.image_compression_controller import CompressionController


def test_mock_page_initialization(mock_page):
    """Verifies that mock_page fixture correctly initializes base page attributes."""
    assert mock_page.route == "/"
    assert mock_page.overlay == []
    assert mock_page.dialog is None


def test_add_control_to_mock_page(mock_page):
    """Tests adding UI controls to the mocked page without triggering protocol exceptions."""
    button = ft.ElevatedButton(text="Click Here")
    mock_page.add(button)

    mock_page.add.assert_called_once_with(button)


def test_dialog_open_simulation(mock_page):
    """Tests opening and rendering dialog boxes on the mocked page."""
    dialog = ft.AlertDialog(title=ft.Text("Notice"))
    mock_page.dialog = dialog
    mock_page.open(dialog)

    assert mock_page.dialog == dialog
    mock_page.open.assert_called_once_with(dialog)


def test_file_picker_registration(mock_page):
    """Verifies registering a FilePicker component into the page overlay layer."""
    file_picker = ft.FilePicker()
    mock_page.overlay.append(file_picker)

    assert file_picker in mock_page.overlay
    assert len(mock_page.overlay) == 1


def test_navigation_destination_change(mock_page):
    """Simulates UI route navigation and tab switches."""
    mock_page.route = "/settings"
    mock_page.go("/settings")

    mock_page.go.assert_called_once_with("/settings")
    assert mock_page.route == "/settings"


def test_button_click_event_handler():
    """Validates click event callback invocation on UI buttons."""
    handler_called = False

    def on_click(e):
        nonlocal handler_called
        handler_called = True

    button = ft.ElevatedButton(text="Process", on_click=on_click)

    if callable(button.on_click):
        button.on_click(MagicMock())

    assert handler_called is True


def test_progress_bar_state_update():
    """Tests updating state and visibility properties on progress bars."""
    progress_bar = ft.ProgressBar(value=0.0, visible=False)

    progress_bar.value = 0.75
    progress_bar.visible = True

    assert progress_bar.value == 0.75
    assert progress_bar.visible is True


def test_banner_and_snack_bar_simulation(mock_page):
    """Tests triggering temporary snack bars and banner notifications."""
    text_control = ft.Text("Compression completed successfully!")
    snack_bar = ft.SnackBar(content=text_control)
    mock_page.snack_bar = snack_bar
    mock_page.snack_bar.open = True

    assert mock_page.snack_bar.open is True
    assert isinstance(mock_page.snack_bar.content, ft.Text)
    assert mock_page.snack_bar.content.value == "Compression completed successfully!"


def test_ui_log_reflects_failed_compression(tmp_workspace, mock_page):
    """Tests controller and UI integration ensuring batch processing failures write '[FAIL]' logs instead of false positives."""
    in_dir, out_dir = tmp_workspace

    # Create a corrupted image file to force engine-level failure
    corrupted_file = in_dir / "bad_image.png"
    corrupted_file.write_bytes(b"NOT_A_VALID_IMAGE_HEADER")

    # Configure controller and mock UI components
    controller = CompressionController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    # Intercept summary dialog invocation to inspect injected summary payload
    with patch("ui.controllers.image_compression_controller.show_summary_dialog") as mock_show_dialog:
        # Execute batch processing synchronously in test environment
        controller._run_batch_compression(
            page=mock_page,
            quality=80,
            lbl_status=lbl_status,
            progress_bar=progress_bar,
            btn_action=btn_action,
        )

        mock_show_dialog.assert_called_once()

        # Extract summary payload dictionary passed to summary dialog
        summary_payload = (
            mock_show_dialog.call_args[0][1]
            if len(mock_show_dialog.call_args[0]) > 1
            else mock_show_dialog.call_args[1].get("summary")
        )

        # Validate accurate error and success statistics
        assert summary_payload.get("failed", 0) == 1
        assert summary_payload.get("success", 0) == 0

        # Verify terminal log contains [FAIL] tag and no false positive [OK] tags
        terminal_log = summary_payload.get("terminal_log", "")
        assert "[FAIL]" in terminal_log
        assert "[OK]" not in terminal_log