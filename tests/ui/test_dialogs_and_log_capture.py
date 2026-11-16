"""Tests for UI dialogs, size/percentage formatting, log tag colors, and stdout/stderr redirection."""

import sys

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
    """Ensures explicit bracket tags take precedence over file name keywords."""
    from ui.components.dialog_utils import get_log_line_color
    from ui.theme import get_color

    # Regression: [FAIL] tags with file names containing "compressed" or "converted" must return error color
    assert get_log_line_color("[FAIL] photo_compressed.png") == get_color("error"), (
        "[ui] Explicit [FAIL] tag must take precedence over 'compressed' in filename and return error color."
    )
    assert get_log_line_color("[FAIL] video_converted.mp4") == get_color("error"), (
        "[ui] Explicit [FAIL] tag must take precedence over 'converted' in filename and return error color."
    )
    assert get_log_line_color("[ERROR] file_success.jpg") == get_color("error"), (
        "[ui] Explicit [ERROR] tag must take precedence over 'success' in filename and return error color."
    )

    # Valid [OK] logs
    assert get_log_line_color("[OK] photo_compressed.png") == get_color("success"), (
        "[ui] Explicit [OK] tag must resolve to success theme color."
    )
    assert get_log_line_color("[OK] video_converted.mp4") == get_color("success"), (
        "[ui] Explicit [OK] tag on converted file log must resolve to success theme color."
    )

    # Explicit warning tag
    assert get_log_line_color("[WARNING] slow compression") == get_color("warning"), (
        "[ui] Explicit [WARNING] tag must resolve to warning theme color."
    )

    # Keyword fallback checks
    assert get_log_line_color("An exception occurred") == get_color("error"), (
        "[ui] Untagged log line mentioning 'exception' must fall back to error theme color."
    )
    assert get_log_line_color("Warning: low disk space") == get_color("warning"), (
        "[ui] Untagged log line starting with 'Warning:' must fall back to warning theme color."
    )
    assert get_log_line_color("Successfully converted file") == get_color("success"), (
        "[ui] Untagged log line with 'Successfully' must fall back to success theme color."
    )
    assert get_log_line_color("Processing starting now...") == get_color("subtext"), (
        "[ui] Neutral informational log line must default to subtext theme color."
    )


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


def test_text_redirector_handles_none_standard_streams(monkeypatch):
    """Ensures TextRedirector works without AttributeError when sys.stdout/sys.stderr are None (windowed builds)."""
    from ui.utils.log_capture import TextRedirector

    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    redirector = TextRedirector()
    redirector.start()
    try:
        print("[OK] processed sample.mp4")
        sys.stdout.flush()
    finally:
        redirector.stop()

    assert "[OK] processed sample.mp4" in redirector.get_logs(), (
        "[ui] TextRedirector failed to buffer stdout output when underlying sys.stdout was None."
    )
    assert sys.stdout is None, (
        "[ui] TextRedirector.stop() failed to restore original None sys.stdout stream."
    )
    assert sys.stderr is None, (
        "[ui] TextRedirector.stop() failed to restore original None sys.stderr stream."
    )
