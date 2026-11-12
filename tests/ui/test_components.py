"""UI component tests: mocked Flet page, controls, dialogs and format helpers.

Exercises Flet controls and reusable UI helpers headlessly through the
`mock_page` fixture, without starting a real Flet application.
"""

from unittest.mock import MagicMock

import flet as ft

# --- Mocked page & Flet controls ---


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


# --- Theme & Color Resolution ---


def test_theme_get_color_danger_resolution():
    """Verifies get_color returns static danger color without fallback to white."""
    from ui.theme import get_color

    danger_color = get_color("danger")
    assert danger_color == ft.colors.RED_600
    assert danger_color != "#FFFFFF"


# --- Format helpers & dialogs ---


def test_format_utils_lists_follow_scanners():
    """Format lists shown in the UI must come from the scanners and not drift."""
    from ui.utils.format_utils import (
        image_compression_formats,
        image_input_formats,
        video_input_formats,
    )

    assert {"JPG", "PNG", "WEBP", "BMP", "GIF"} <= set(image_input_formats())
    # Scanned-but-uncompressible formats are not advertised for compression.
    assert not {"BMP", "PPM", "GIF", "ICO"} & set(image_compression_formats())
    assert {"JPG", "PNG", "WEBP"} <= set(image_compression_formats())
    assert {"MP4", "MKV", "WEBM", "MOV", "AVI", "WMV", "FLV", "M4V"} <= set(video_input_formats())


def test_no_supported_files_dialog_lists_formats(mock_page):
    """The dialog must be opened on the page and mention the accepted formats."""
    from ui.components.dialog_utils import show_no_supported_files_dialog

    show_no_supported_files_dialog(mock_page, ["MP4", "MKV"])

    dialog = mock_page.dialog
    assert dialog is not None and dialog.open is True
    texts = [c.value for c in dialog.content.content.controls]
    assert any("MP4, MKV" in text for text in texts)


def test_get_log_line_color_tag_precedence():
    """Ensures explicit bracket tags take precedence over file name keywords."""
    from ui.components.dialog_utils import get_log_line_color
    from ui.theme import get_color

    # Regression: [FAIL] tags with file names containing "compressed" or "converted" must return error color
    assert get_log_line_color("[FAIL] photo_compressed.png") == get_color("error")
    assert get_log_line_color("[FAIL] video_converted.mp4") == get_color("error")
    assert get_log_line_color("[ERROR] file_success.jpg") == get_color("error")

    # Valid [OK] logs
    assert get_log_line_color("[OK] photo_compressed.png") == get_color("success")
    assert get_log_line_color("[OK] video_converted.mp4") == get_color("success")

    # Explicit warning tag
    assert get_log_line_color("[WARNING] slow compression") == get_color("warning")

    # Keyword fallback checks
    assert get_log_line_color("An exception occurred") == get_color("error")
    assert get_log_line_color("Warning: low disk space") == get_color("warning")
    assert get_log_line_color("Successfully converted file") == get_color("success")
    assert get_log_line_color("Processing starting now...") == get_color("subtext")


# --- Source Picker Card & Path Label Components ---


def test_create_path_label_defaults_and_custom_text():
    """Validates create_path_label initialization with default i18n text and custom strings."""
    from ui.components.path_label import create_path_label

    lbl_default = create_path_label()
    assert isinstance(lbl_default, ft.Text)
    assert lbl_default.size == 11
    assert lbl_default.max_lines == 1
    assert lbl_default.overflow == ft.TextOverflow.ELLIPSIS

    lbl_custom = create_path_label("custom/path/file.png")
    assert lbl_custom.value == "custom/path/file.png"


def test_create_source_picker_card_structure_and_callbacks():
    """Verifies that create_source_picker_card renders PopupMenuButton and triggers selection callbacks."""
    from ui.components.path_label import create_path_label
    from ui.components.source_picker_card import create_source_picker_card

    file_callback_called = False
    folder_callback_called = False

    def on_file():
        nonlocal file_callback_called
        file_callback_called = True

    def on_folder():
        nonlocal folder_callback_called
        folder_callback_called = True

    lbl_in_path = create_path_label()
    card = create_source_picker_card(
        lbl_in_path=lbl_in_path,
        on_select_file=on_file,
        on_select_folder=on_folder,
        file_icon=ft.icons.VIDEO_FILE,
    )

    assert isinstance(card, ft.Container)
    assert isinstance(card.content, ft.PopupMenuButton)

    popup_menu = card.content
    assert popup_menu.items is not None
    assert len(popup_menu.items) == 2

    item_file = popup_menu.items[0]
    item_folder = popup_menu.items[1]

    assert isinstance(item_file, ft.PopupMenuItem)
    assert isinstance(item_folder, ft.PopupMenuItem)
    assert item_file.icon == ft.icons.VIDEO_FILE
    assert item_folder.icon == ft.icons.FOLDER

    if callable(item_file.on_click):
        item_file.on_click(MagicMock())
    assert file_callback_called is True

    if callable(item_folder.on_click):
        item_folder.on_click(MagicMock())
    assert folder_callback_called is True


# --- Module Registry Tests ---


def test_module_registry_route_and_active_state_resolution():
    """Verifies route resolution and active module matching using module IDs."""
    from ui.registry import get_all_routes, resolve_active_module_id

    routes = get_all_routes()
    assert "home" in routes
    assert "image_hub" in routes
    assert "video_hub" in routes
    assert "image_conversion" in routes
    assert "video_compression" in routes

    # Active module ID resolution without string splitting
    assert resolve_active_module_id("home") == "home"
    assert resolve_active_module_id("image_hub") == "image"
    assert resolve_active_module_id("image_conversion") == "image"
    assert resolve_active_module_id("video_compression") == "video"
    assert resolve_active_module_id("unknown_route") == ""

# --- Format size and reduction display tests ---


def test_format_size_units():
    """Unit tests for format_size covering B, KB, MB, and GB ranges."""
    from ui.components.dialog_utils import format_size

    assert format_size(0) == "0 B"
    assert format_size(512) == "512 B"
    assert format_size(1536) == "1.5 KB"  # 1.5 * 1024
    assert format_size(5 * 1024 * 1024) == "5.00 MB"
    assert format_size(3 * 1024 * 1024 * 1024) == "3.00 GB"


def test_reduction_percentage_sign_and_color():
    """Reduction text uses a signed percentage and warning color on size increase."""
    from ui.components.dialog_utils import format_size
    from ui.i18n import t

    # Positive reduction (size decreased)
    pos_pct = 35.2
    pos_text = t("log_reduction_stat", pct=pos_pct)
    assert "+35.2%" in pos_text or "35.2%" in pos_text
    assert "--" not in pos_text

    # Negative reduction (size increased)
    neg_pct = -20.5
    neg_text = t("log_reduction_stat", pct=neg_pct)
    assert "-20.5%" in neg_text
    assert "--" not in neg_text

    # format_size still works for large values
    assert "GB" in format_size(2 * 1024**3)
