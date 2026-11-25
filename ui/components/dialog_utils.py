import logging
from typing import Any

import flet as ft

from src.utils.file_result import LogLevel
from ui.i18n import t
from ui.theme import get_color
from ui.utils.log_capture import LogEntry

# Setup module logger
logger = logging.getLogger(__name__)

_LOG_LEVEL_COLOR_KEYS: dict[LogLevel, str] = {
    LogLevel.INFO: "subtext",
    LogLevel.SUCCESS: "success",
    LogLevel.WARNING: "warning",
    LogLevel.ERROR: "error",
}


def format_size(size_bytes: int) -> str:
    """Formats byte count into human-readable string representation.

    Args:
        size_bytes: The total size in bytes to be formatted.

    Returns:
        Formatted string representing size in B, KB, MB or GB.
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    kb = size_bytes / 1024
    if kb >= 1024 * 1024:
        return f"{kb / (1024 * 1024):.2f} GB"
    if kb >= 1024:
        return f"{kb / 1024:.2f} MB"
    return f"{kb:.1f} KB"


def get_log_line_color(level: LogLevel) -> str:
    """Resolves the theme color hex for a log line strictly from its semantic LogLevel.

    Args:
        level: Semantic LogLevel associated with the log entry.

    Returns:
        Theme hexadecimal color string (e.g., 'error', 'success', 'warning', 'subtext').
    """
    color_key = _LOG_LEVEL_COLOR_KEYS.get(level, "subtext")
    return get_color(color_key)


def show_summary_dialog(page: ft.Page, summary: dict[str, Any]) -> None:
    """Displays modal dialog rendering execution metrics, file size stats, and colored logs.

    Args:
        page: Active Flet Page instance to present the modal.
        summary: Dictionary containing process statistics, file lists, and execution logs.
    """
    success = summary.get("success", summary.get("successful", 0))
    skipped = summary.get("skipped", 0)
    failed = summary.get("failed", 0)
    total = summary.get("total_files", summary.get("total"))
    if total is None:
        total = success + skipped + failed
    elapsed = summary.get("elapsed_seconds", 0.0)
    errors = summary.get("errors", [])

    orig_bytes = summary.get("original_bytes", 0)
    comp_bytes = summary.get("compressed_bytes", 0)
    file_details: list[dict[str, Any]] = summary.get("files", [])
    log_entries: list[LogEntry] = summary.get("log_entries", [])
    terminal_log: str = summary.get("terminal_log", "").strip()

    reduction_pct = 0.0
    if orig_bytes > 0:
        reduction_pct = ((orig_bytes - comp_bytes) / orig_bytes) * 100

    log_items: list[ft.Control] = []
    raw_log_text_list: list[str] = []

    # Priority 1: Render structured log entries colored strictly by LogLevel
    if log_entries:
        for entry in log_entries:
            line_str = entry.message.strip()
            if not line_str:
                continue

            raw_log_text_list.append(line_str)
            log_items.append(
                ft.Text(
                    line_str,
                    size=11,
                    color=get_log_line_color(entry.level),
                    font_family="monospace",
                    selectable=True,
                )
            )

    # Priority 2: Plain terminal_log fallback without keyword matching
    elif terminal_log:
        for line in terminal_log.splitlines():
            line_str = line.strip()
            if not line_str:
                continue

            raw_log_text_list.append(line_str)
            log_items.append(
                ft.Text(
                    line_str,
                    size=11,
                    color=get_log_line_color(LogLevel.INFO),
                    font_family="monospace",
                    selectable=True,
                )
            )

    # Priority 3: Render structured file details list
    elif file_details:
        for item in file_details:
            fname = item.get("name", "Unknown")
            item_orig = item.get("orig_bytes", 0)
            item_comp = item.get("comp_bytes", 0)
            item_skipped = item.get("skipped", False)
            item_success = item.get("success", True)
            item_err = item.get("error", "")

            if item_skipped:
                reason_key = item.get("skip_reason_key")
                reason_params = item.get("skip_reason_params") or {}
                reason = t(reason_key, **reason_params) if reason_key else ""
                skip_line = (
                    f"[SKIP] {fname} - {reason}" if reason else f"[SKIP] {fname}"
                )
                raw_log_text_list.append(skip_line)
                log_items.append(
                    ft.Text(
                        skip_line,
                        size=11,
                        color=get_log_line_color(LogLevel.WARNING),
                        font_family="monospace",
                    )
                )
            elif not item_success:
                err_line = f"[FAIL] {fname}: {item_err or t('msg_error')}"
                raw_log_text_list.append(err_line)
                log_items.append(
                    ft.Text(
                        err_line,
                        size=11,
                        color=get_log_line_color(LogLevel.ERROR),
                        font_family="monospace",
                    )
                )
            else:
                item_pct = 0.0
                if item_orig > 0:
                    item_pct = ((item_orig - item_comp) / item_orig) * 100

                orig_str = format_size(item_orig)
                comp_str = format_size(item_comp)
                item_sign = "-" if item_pct >= 0 else "+"
                ok_line = (
                    f"[OK] {fname:<25} | {orig_str} -> {comp_str} "
                    f"| {item_sign}{abs(item_pct):.1f}%"
                )
                raw_log_text_list.append(ok_line)

                log_items.append(
                    ft.Text(
                        ok_line,
                        size=11,
                        color=get_log_line_color(LogLevel.SUCCESS),
                        font_family="monospace",
                    )
                )

    # Priority 4: Render standalone error logs
    elif errors:
        for err in errors:
            file_name = err.get("file", "Unknown")
            reason = err.get("error", "Unspecified error")
            err_line = f"[ERROR] {file_name}: {reason}"
            raw_log_text_list.append(err_line)
            log_items.append(
                ft.Text(
                    err_line,
                    size=11,
                    color=get_log_line_color(LogLevel.ERROR),
                    font_family="monospace",
                )
            )
    else:
        no_err_line = f"[OK] {t('log_no_errors')}"
        raw_log_text_list.append(no_err_line)
        log_items.append(
            ft.Text(
                no_err_line,
                size=11,
                color=get_log_line_color(LogLevel.SUCCESS),
            )
        )

    full_plain_log = "\n".join(raw_log_text_list)

    async def _copy_and_notify() -> None:
        await ft.Clipboard().set(full_plain_log)
        page.show_dialog(
            ft.SnackBar(
                content=ft.Text(t("msg_log_copied")),
                duration=2000,
            )
        )

    def copy_log_to_clipboard(_: Any) -> None:
        """Copies the accumulated console output to system clipboard."""
        if full_plain_log:
            page.run_task(_copy_and_notify)

    btn_copy_log = ft.IconButton(
        icon=ft.Icons.COPY,
        icon_size=16,
        tooltip=t("btn_copy_log"),
        on_click=copy_log_to_clipboard,
    )

    def toggle_logs(_: Any) -> None:
        """Toggles detail log container visibility."""
        log_container.visible = not log_container.visible
        btn_toggle_log.content = (
            t("log_btn_hide_logs") if log_container.visible else t("log_btn_view_logs")
        )
        dialog.update()

    btn_toggle_log = ft.TextButton(
        content=t("log_btn_hide_logs"),
        icon=ft.Icons.LIST_ALT,
        on_click=toggle_logs,
    )

    # Header controls row containing toggle and copy buttons
    actions_row = ft.Row(
        [
            btn_toggle_log,
            btn_copy_log,
        ],
        alignment=ft.MainAxisAlignment.START,
        spacing=8,
    )

    log_container = ft.Column(
        controls=[
            ft.Text(
                t("log_detail_title"),
                size=12,
                weight=ft.FontWeight.BOLD,
                color=get_color("text"),
            ),
            ft.Container(
                content=ft.Column(
                    log_items,
                    scroll=ft.ScrollMode.ALWAYS,
                    auto_scroll=True,
                    spacing=2,
                    expand=True,
                ),
                bgcolor=ft.Colors.BLACK_26,
                padding=12,
                border_radius=8,
                height=180,
                width=380,
            ),
        ],
        visible=True,
        spacing=6,
    )

    def close_dialog(_: Any) -> None:
        """Closes summary dialog modal."""
        dialog.open = False
        page.pop_dialog()
        page.update()

    summary_info: list[ft.Control] = [
        ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(
                            t("log_summary_total"), size=11, color=get_color("subtext")
                        ),
                        ft.Text(
                            str(total),
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            color=get_color("text"),
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Column(
                    [
                        ft.Text(
                            t("log_summary_success"),
                            size=11,
                            color=get_color("subtext"),
                        ),
                        ft.Text(
                            str(success),
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            color=get_color("success"),
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Column(
                    [
                        ft.Text(
                            t("log_summary_skipped"),
                            size=11,
                            color=get_color("subtext"),
                        ),
                        ft.Text(
                            str(skipped),
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            color=get_color("warning")
                            if skipped > 0
                            else get_color("text"),
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Column(
                    [
                        ft.Text(
                            t("log_summary_failed"), size=11, color=get_color("subtext")
                        ),
                        ft.Text(
                            str(failed),
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            color=get_color("error")
                            if failed > 0
                            else get_color("text"),
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_AROUND,
        ),
        ft.Divider(height=10, color=get_color("subtext")),
    ]

    if orig_bytes > 0:
        if reduction_pct >= 0:
            reduction_text = t("log_reduction_stat", pct=reduction_pct)
            reduction_color = get_color("success")
        else:
            reduction_text = t("log_increase_stat", pct=abs(reduction_pct))
            reduction_color = get_color("warning")
        summary_info.append(
            ft.Row(
                [
                    ft.Text(
                        t(
                            "log_size_stat",
                            orig=format_size(orig_bytes),
                            comp=format_size(comp_bytes),
                        ),
                        size=12,
                        color=get_color("text"),
                        weight=ft.FontWeight.W_500,
                    ),
                    ft.Text(
                        reduction_text,
                        size=12,
                        color=reduction_color,
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
        )

    summary_info.extend(
        [
            ft.Text(
                f"{t('log_summary_time')}: {elapsed:.2f}s",
                size=12,
                color=get_color("subtext"),
            ),
            actions_row,
            log_container,
        ]
    )

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.ASSESSMENT, color=get_color("primary")),
                ft.Text(
                    t("log_dialog_title"),
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=get_color("text"),
                ),
            ],
            spacing=10,
        ),
        content=ft.Container(
            width=420,
            content=ft.Column(
                summary_info,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10,
                tight=True,
            ),
        ),
        actions=list[ft.Control]([
            ft.Button(
                content=t("btn_ok"),
                bgcolor=get_color("primary"),
                color=get_color("text"),
                on_click=close_dialog,
            )
        ]),
        actions_alignment=ft.MainAxisAlignment.END,
    )

    page.show_dialog(dialog)


def show_no_supported_files_dialog(page: ft.Page, formats: list[str]) -> None:
    """Warns that the selected folder has no files the operation can process.

    Replaces the success message and the results dialog when a batch finds
    zero supported files, listing the formats the module accepts.

    Args:
        page: Active Flet Page instance to present the modal.
        formats: Upper-case format names accepted by the calling module.
    """

    def close_dialog(_: Any) -> None:
        """Closes the no supported files dialog."""
        dialog.open = False
        page.pop_dialog()
        page.update()

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=get_color("warning")),
                ft.Text(
                    t("dialog_no_files_title"),
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=get_color("text"),
                ),
            ],
            spacing=10,
        ),
        content=ft.Container(
            width=420,
            content=ft.Column(
                [
                    ft.Text(t("dialog_no_files_body"), size=13),
                    ft.Text(
                        t("dialog_no_files_formats", formats=", ".join(formats)),
                        size=12,
                        weight=ft.FontWeight.W_600,
                        color=get_color("subtext"),
                        selectable=True,
                    ),
                ],
                spacing=12,
                tight=True,
            ),
        ),
        actions=list[ft.Control]([
            ft.Button(
                content=t("btn_ok"),
                bgcolor=get_color("primary"),
                color=get_color("text"),
                on_click=close_dialog,
            )
        ]),
        actions_alignment=ft.MainAxisAlignment.END,
    )

    page.show_dialog(dialog)
