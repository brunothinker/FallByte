"""UI: tests for dialog_utils, pickers, path_label, and other components."""

from typing import Any, cast
from unittest.mock import MagicMock

import flet as ft


def _collect_texts(control):
    """Recursively collects every ft.Text control from a control tree."""
    texts = []
    if isinstance(control, ft.Text):
        texts.append(control)
    for child in getattr(control, "controls", None) or []:
        texts.extend(_collect_texts(child))
    content = getattr(control, "content", None)
    if content is not None:
        texts.extend(_collect_texts(content))
    return texts


def test_no_supported_files_dialog_lists_formats(mock_page):
    """The dialog must be opened on the page and mention the accepted formats."""
    from ui.components.dialog_utils import show_no_supported_files_dialog

    show_no_supported_files_dialog(mock_page, ["MP4", "MKV"])

    dialog = mock_page.dialog
    assert dialog is not None and dialog.open is True, (
        "[ui] show_no_supported_files_dialog() must assign an open AlertDialog to page.dialog."
    )
    texts = [c.value for c in dialog.content.content.controls]
    assert any("MP4, MKV" in text for text in texts), (
        "[ui] Unsupported-files dialog body must list the accepted formats ('MP4, MKV') for user guidance."
    )


def test_get_log_line_color_tag_precedence():
    """Ensures log color is determined strictly by LogLevel, ignoring filename keywords."""
    from src.utils.file_result import FileResult, LogLevel
    from ui.components.dialog_utils import get_log_line_color
    from ui.controllers.base_controller import BaseController
    from ui.theme import get_color

    # Regression: FAILED result with file name containing "compressed" or "converted" must return error color
    level, line = BaseController._format_result_entry(
        "photo_compressed.png", FileResult.failed()
    )
    assert level is LogLevel.ERROR
    assert "[FAIL] photo_compressed.png" in line
    assert get_log_line_color(level) == get_color("error")


def test_format_size_units():
    """Covers bytes, KB, MB and GB ranges (issue #58 acceptance criteria)."""
    from ui.components.dialog_utils import format_size

    assert format_size(0) == "0 B", (
        "[ui] format_size(0) must format zero bytes as '0 B'."
    )
    assert format_size(512) == "512 B", (
        "[ui] format_size(512) must keep sub-kilobyte values in bytes ('512 B')."
    )
    assert format_size(1536) == "1.5 KB", (
        "[ui] format_size(1536) must format kilobyte values with one decimal ('1.5 KB')."
    )
    assert format_size(5 * 1024 * 1024) == "5.00 MB", (
        "[ui] format_size(5 MiB) must format megabyte values with two decimals ('5.00 MB')."
    )
    assert format_size(3 * 1024 * 1024 * 1024) == "3.00 GB", (
        "[ui] format_size(3 GiB) must format gigabyte values with two decimals ('3.00 GB')."
    )


def test_summary_dialog_reduction_shows_single_sign_with_success_color(mock_page):
    """A real reduction renders one minus sign and the success color."""
    from ui.components.dialog_utils import show_summary_dialog
    from ui.theme import get_color

    show_summary_dialog(
        mock_page,
        {
            "total_files": 1,
            "success": 1,
            "failed": 0,
            "elapsed_seconds": 1.0,
            "original_bytes": 1000,
            "compressed_bytes": 500,
            "files": [],
        },
    )
    reduction_rows = [
        text
        for text in _collect_texts(mock_page.dialog)
        if text.value and "%" in text.value
    ]
    assert len(reduction_rows) == 1, (
        "[ui] Summary dialog must render exactly one reduction percentage row."
    )
    assert reduction_rows[0].value.count("--") == 0, (
        "[ui] Summary dialog reduction percentage must never render a double minus sign '--'."
    )
    assert reduction_rows[0].value.endswith("-50.0%"), (
        "[ui] 50% byte savings must render with a single leading minus sign ('-50.0%')."
    )
    assert reduction_rows[0].color == get_color("success"), (
        "[ui] Positive size reduction row must be highlighted with the success theme color."
    )


def test_summary_dialog_size_growth_never_doubles_minus(mock_page):
    """When output is larger, the stat must not render a double minus and must use warning color."""
    from ui.components.dialog_utils import show_summary_dialog
    from ui.theme import get_color

    show_summary_dialog(
        mock_page,
        {
            "total_files": 1,
            "success": 1,
            "failed": 0,
            "elapsed_seconds": 1.0,
            "original_bytes": 1000,
            "compressed_bytes": 1352,
            "files": [],
        },
    )
    grown_rows = [
        text
        for text in _collect_texts(mock_page.dialog)
        if text.value and "%" in text.value
    ]
    assert len(grown_rows) == 1, (
        "[ui] Summary dialog must render a single size-increase row when output is larger than input."
    )
    assert "--" not in grown_rows[0].value, (
        "[ui] Summary dialog percentage row must never contain a double minus '--' on size growth."
    )
    assert grown_rows[0].color == get_color("warning"), (
        "[ui] Size increase row in summary dialog must use the warning theme color."
    )
    assert grown_rows[0].value.endswith("+35.2%"), (
        "[ui] Size growth of 35.2% must render with an explicit leading plus sign ('+35.2%')."
    )


def test_summary_dialog_per_file_line_never_doubles_minus(mock_page):
    """Structured per-file log lines must not render a double minus when a file grew."""
    from ui.components.dialog_utils import show_summary_dialog

    show_summary_dialog(
        mock_page,
        {
            "total_files": 1,
            "success": 1,
            "failed": 0,
            "elapsed_seconds": 1.0,
            "original_bytes": 0,
            "compressed_bytes": 0,
            "files": [
                {
                    "name": "grown.png",
                    "orig_bytes": 1000,
                    "comp_bytes": 1352,
                    "success": True,
                }
            ],
        },
    )
    log_lines = [
        text.value
        for text in _collect_texts(mock_page.dialog)
        if text.value and text.value.startswith("[OK]")
    ]
    assert len(log_lines) == 1, (
        "[ui] Summary dialog must render one [OK] per-file log line for the processed item."
    )
    assert "--" not in log_lines[0], (
        "[ui] Per-file log line in summary dialog must not render a double minus '--' when file size increased."
    )


def test_summary_dialog_displays_skipped_count_and_skip_lines(mock_page):
    """Summary dialog must render the skipped metric column and [SKIP] per-file log lines in warning color."""
    from ui.components.dialog_utils import show_summary_dialog
    from ui.i18n import t
    from ui.theme import get_color

    show_summary_dialog(
        mock_page,
        {
            "total_files": 3,
            "success": 1,
            "skipped": 2,
            "failed": 0,
            "elapsed_seconds": 1.5,
            "original_bytes": 0,
            "compressed_bytes": 0,
            "files": [
                {
                    "name": "same.mp4",
                    "skipped": True,
                    "skip_reason_key": "skip_same_format",
                    "skip_reason_params": {"fmt": "mp4"},
                }
            ],
        },
    )
    texts = _collect_texts(mock_page.dialog)

    skipped_counts = [
        txt for txt in texts if txt.value == "2" and txt.color == get_color("warning")
    ]
    assert len(skipped_counts) == 1, (
        "[ui] Summary dialog must highlight a non-zero skipped count with warning color."
    )

    skip_lines = [
        txt for txt in texts if txt.value and txt.value.startswith("[SKIP] same.mp4")
    ]
    assert len(skip_lines) == 1, (
        "[ui] Summary dialog must render a [SKIP] per-file log line for skipped items."
    )
    assert t("skip_same_format", fmt="mp4") in skip_lines[0].value, (
        "[ui] [SKIP] per-file log line must include the translated skip reason."
    )
    assert skip_lines[0].color == get_color("warning"), (
        "[ui] [SKIP] per-file log line must use the warning theme color."
    )


def test_create_path_label_defaults_and_custom_text():
    """Validates create_path_label initialization with default i18n text and custom strings."""
    from ui.components.path_label import create_path_label

    lbl_default = create_path_label()
    assert isinstance(lbl_default, ft.Text), (
        "[ui] create_path_label() must return an ft.Text control."
    )
    assert lbl_default.size == 11, (
        "[ui] Path label font size must default to 11px for compact card layout."
    )
    assert lbl_default.max_lines == 1, (
        "[ui] Path label must restrict text to a single line (max_lines=1) to prevent card overflow."
    )
    assert lbl_default.overflow == ft.TextOverflow.ELLIPSIS, (
        "[ui] Path label must truncate long paths with TextOverflow.ELLIPSIS."
    )

    lbl_custom = create_path_label("custom/path/file.png")
    assert lbl_custom.value == "custom/path/file.png", (
        "[ui] create_path_label() must display the caller-provided custom path string."
    )


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
        file_icon=ft.Icons.VIDEO_FILE,
    )

    assert isinstance(card, ft.Container), (
        "[ui] create_source_picker_card() must wrap the picker trigger in an ft.Container."
    )
    assert isinstance(card.content, ft.PopupMenuButton), (
        "[ui] Source picker card content must be an ft.PopupMenuButton offering file/folder choice."
    )

    popup_menu = card.content
    assert popup_menu.items is not None, (
        "[ui] Source picker PopupMenuButton must define selectable menu items."
    )
    assert len(popup_menu.items) == 2, (
        "[ui] Source picker PopupMenuButton must expose exactly 2 items (file and folder)."
    )

    item_file = popup_menu.items[0]
    item_folder = popup_menu.items[1]

    assert isinstance(item_file, ft.PopupMenuItem), (
        "[ui] First source picker menu entry must be an ft.PopupMenuItem for file selection."
    )
    assert isinstance(item_folder, ft.PopupMenuItem), (
        "[ui] Second source picker menu entry must be an ft.PopupMenuItem for folder selection."
    )
    assert item_file.icon == ft.Icons.VIDEO_FILE, (
        "[ui] File menu item must use the custom file_icon passed to create_source_picker_card()."
    )
    assert item_folder.icon == ft.Icons.FOLDER, (
        "[ui] Folder menu item must display the standard ft.Icons.FOLDER icon."
    )

    if callable(item_file.on_click):
        cast(Any, item_file.on_click)(MagicMock())
    assert file_callback_called is True, (
        "[ui] Clicking the file PopupMenuItem must invoke on_select_file callback."
    )

    if callable(item_folder.on_click):
        cast(Any, item_folder.on_click)(MagicMock())
    assert folder_callback_called is True, (
        "[ui] Clicking the folder PopupMenuItem must invoke on_select_folder callback."
    )
