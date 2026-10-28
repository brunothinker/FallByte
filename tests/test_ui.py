from unittest.mock import MagicMock

import flet as ft


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