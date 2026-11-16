"""Headless Flet page double and basic Flet control interaction tests."""

from unittest.mock import MagicMock

import flet as ft


def test_mock_page_initialization(mock_page):
    """Verifies that mock_page fixture correctly initializes base page attributes."""
    assert mock_page.route == "/", (
        "[ui] Mock page fixture must initialize with default root route '/'."
    )
    assert mock_page.overlay == [], (
        "[ui] Mock page fixture must initialize with an empty overlay list."
    )
    assert mock_page.dialog is None, (
        "[ui] Mock page fixture must initialize with no active dialog (dialog is None)."
    )


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

    assert mock_page.dialog == dialog, (
        "[ui] Assigning AlertDialog to mock_page.dialog must retain the dialog reference."
    )
    mock_page.open.assert_called_once_with(dialog)


def test_file_picker_registration(mock_page):
    """Verifies registering a FilePicker component into the page overlay layer."""
    file_picker = ft.FilePicker()
    mock_page.overlay.append(file_picker)

    assert file_picker in mock_page.overlay, (
        "[ui] Registered FilePicker must be present in page.overlay for Flet protocol delivery."
    )
    assert len(mock_page.overlay) == 1, (
        "[ui] Registering a single FilePicker must result in exactly 1 overlay item."
    )


def test_navigation_destination_change(mock_page):
    """Simulates UI route navigation and tab switches."""
    mock_page.route = "/settings"
    mock_page.go("/settings")

    mock_page.go.assert_called_once_with("/settings")
    assert mock_page.route == "/settings", (
        "[ui] Navigating to '/settings' must update mock_page.route accordingly."
    )


def test_button_click_event_handler():
    """Validates click event callback invocation on UI buttons."""
    handler_called = False

    def on_click(e):
        nonlocal handler_called
        handler_called = True

    button = ft.ElevatedButton(text="Process", on_click=on_click)

    if callable(button.on_click):
        button.on_click(MagicMock())

    assert handler_called is True, (
        "[ui] Invoking ElevatedButton.on_click must execute the bound click callback."
    )


def test_progress_bar_state_update():
    """Tests updating state and visibility properties on progress bars."""
    progress_bar = ft.ProgressBar(value=0.0, visible=False)

    progress_bar.value = 0.75
    progress_bar.visible = True

    assert progress_bar.value == 0.75, (
        "[ui] ProgressBar.value must reflect updated completion ratio 0.75."
    )
    assert progress_bar.visible is True, (
        "[ui] ProgressBar.visible must become True when shown during active processing."
    )


def test_banner_and_snack_bar_simulation(mock_page):
    """Tests triggering temporary snack bars and banner notifications."""
    text_control = ft.Text("Compression completed successfully!")
    snack_bar = ft.SnackBar(content=text_control)
    mock_page.snack_bar = snack_bar
    mock_page.snack_bar.open = True

    assert mock_page.snack_bar.open is True, (
        "[ui] Opening SnackBar on mock_page must set snack_bar.open to True."
    )
    assert isinstance(mock_page.snack_bar.content, ft.Text), (
        "[ui] SnackBar content must be preserved as an ft.Text control."
    )
    assert mock_page.snack_bar.content.value == "Compression completed successfully!", (
        "[ui] SnackBar text content must preserve the notification message string."
    )
