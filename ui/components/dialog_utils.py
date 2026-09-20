import logging
from typing import Any, Dict, List
import flet as ft

from ui.i18n import t
from ui.theme import (
    COLOR_CARD_BG,
    COLOR_ERROR,
    COLOR_PRIMARY,
    COLOR_SUBTEXT,
    COLOR_SUCCESS,
    COLOR_TEXT,
)

# Setup module logger
logger = logging.getLogger(__name__)


def format_size(size_bytes: int) -> str:
    """Formats byte count into human-readable string representation.

    Args:
        size_bytes: The total size in bytes to be formatted.

    Returns:
        Formatted string representing size in KB or MB.
    """
    kb = size_bytes / 1024
    if kb >= 1024:
        return f"{kb / 1024:.2f} MB"
    return f"{kb:.1f} KB"


def show_summary_dialog(page: ft.Page, summary: Dict[str, Any]) -> None:
    """Displays modal dialog rendering execution metrics, file size stats, and colored logs.

    Args:
        page: Active Flet Page instance to present the modal.
        summary: Dictionary containing process statistics, file lists, and execution logs.
    """
    success = summary.get("success", summary.get("successful", 0))
    failed = summary.get("failed", 0)
    total = summary.get("total_files", summary.get("total", success + failed))
    elapsed = summary.get("elapsed_seconds", 0.0)
    errors = summary.get("errors", [])

    orig_bytes = summary.get("original_bytes", 0)
    comp_bytes = summary.get("compressed_bytes", 0)
    file_details: List[Dict[str, Any]] = summary.get("files", [])
    terminal_log: str = summary.get("terminal_log", "").strip()

    reduction_pct = 0.0
    if orig_bytes > 0:
        reduction_pct = ((orig_bytes - comp_bytes) / orig_bytes) * 100

    log_items: List[ft.Control] = []
    raw_log_text_list: List[str] = []

    # Priority 1: Render raw terminal output line by line with dynamic colors
    if terminal_log:
        lines = terminal_log.splitlines()
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            raw_log_text_list.append(line_str)
            line_lower = line_str.lower()

            # Match success keywords for green highlighting
            if any(
                k in line_lower
                for k in [
                    "[ok]",
                    "success",
                    "sucesso",
                    "concluído",
                    "converted",
                    "compressed",
                ]
            ):
                text_color = COLOR_SUCCESS
            # Match failure/error keywords for red highlighting
            elif any(
                k in line_lower
                for k in [
                    "[fail]",
                    "[error]",
                    "falha",
                    "erro",
                    "failed",
                    "exception",
                    "traceback",
                ]
            ):
                text_color = COLOR_ERROR
            else:
                text_color = COLOR_SUBTEXT

            log_items.append(
                ft.Text(
                    line_str,
                    size=11,
                    color=text_color,
                    font_family="monospace",
                    selectable=True,
                )
            )

    # Priority 2: Render structured file details list
    elif file_details:
        for item in file_details:
            fname = item.get("name", "Unknown")
            item_orig = item.get("orig_bytes", 0)
            item_comp = item.get("comp_bytes", 0)
            item_success = item.get("success", True)
            item_err = item.get("error", "")

            if not item_success:
                err_line = f"[FAIL] {fname}: {item_err or t('msg_error')}"
                raw_log_text_list.append(err_line)
                log_items.append(
                    ft.Text(
                        err_line,
                        size=11,
                        color=COLOR_ERROR,
                        font_family="monospace",
                    )
                )
            else:
                item_pct = 0.0
                if item_orig > 0:
                    item_pct = ((item_orig - item_comp) / item_orig) * 100

                orig_str = format_size(item_orig)
                comp_str = format_size(item_comp)
                ok_line = f"[OK] {fname:<25} | {orig_str} -> {comp_str} | -{item_pct:.1f}%"
                raw_log_text_list.append(ok_line)

                log_items.append(
                    ft.Text(
                        ok_line,
                        size=11,
                        color=COLOR_SUCCESS,
                        font_family="monospace",
                    )
                )

    # Priority 3: Render standalone error logs
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
                    color=COLOR_ERROR,
                    font_family="monospace",
                )
            )
    else:
        no_err_line = f"[OK] {t('log_no_errors')}"
        raw_log_text_list.append(no_err_line)
        log_items.append(
            ft.Text(no_err_line, size=11, color=COLOR_SUCCESS)
        )

    full_plain_log = "\n".join(raw_log_text_list)

    def copy_log_to_clipboard(_: ft.ControlEvent) -> None:
        """Copies the accumulated console output to system clipboard.

        Args:
            _: The trigger control event instance.
        """
        if full_plain_log:
            page.set_clipboard(full_plain_log)
            page.snack_bar = ft.SnackBar(
                content=ft.Text(
                    t("msg_log_copied")
                    if t("msg_log_copied") != "msg_log_copied"
                    else "Log copiado para a área de transferência!"
                ),
                duration=2000,
            )
            page.snack_bar.open = True
            page.update()

    btn_copy_log = ft.IconButton(
        icon=ft.icons.COPY,
        icon_size=16,
        tooltip=t("btn_copy_log")
        if t("btn_copy_log") != "btn_copy_log"
        else "Copiar Log",
        on_click=copy_log_to_clipboard,
    )

    def toggle_logs(e: ft.ControlEvent) -> None:
        """Toggles detail log container visibility.

        Args:
            e: The trigger control event instance.
        """
        log_container.visible = not log_container.visible
        btn_toggle_log.text = (
            t("log_btn_hide_logs")
            if log_container.visible
            else t("log_btn_view_logs")
        )
        dialog.update()

    btn_toggle_log = ft.TextButton(
        text=t("log_btn_hide_logs"),
        icon=ft.icons.LIST_ALT,
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
                color=COLOR_TEXT,
            ),
            ft.Container(
                content=ft.Column(
                    log_items,
                    scroll=ft.ScrollMode.ALWAYS,
                    auto_scroll=True,
                    spacing=2,
                    expand=True,
                ),
                bgcolor=ft.colors.BLACK26,
                padding=12,
                border_radius=8,
                height=180,
                width=380,
            ),
        ],
        visible=True,
        spacing=6,
    )

    def close_dialog(e: ft.ControlEvent) -> None:
        """Closes summary dialog modal.

        Args:
            e: The trigger control event instance.
        """
        dialog.open = False
        page.update()

    summary_info: List[ft.Control] = [
        ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(
                            t("log_summary_total"), size=11, color=COLOR_SUBTEXT
                        ),
                        ft.Text(
                            str(total),
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            color=COLOR_TEXT,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Column(
                    [
                        ft.Text(
                            t("log_summary_success"),
                            size=11,
                            color=COLOR_SUBTEXT,
                        ),
                        ft.Text(
                            str(success),
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            color=COLOR_SUCCESS,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Column(
                    [
                        ft.Text(
                            t("log_summary_failed"), size=11, color=COLOR_SUBTEXT
                        ),
                        ft.Text(
                            str(failed),
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            color=COLOR_ERROR if failed > 0 else COLOR_TEXT,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_AROUND,
        ),
        ft.Divider(height=10, color=COLOR_SUBTEXT),
    ]

    if orig_bytes > 0:
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
                        color=COLOR_TEXT,
                        weight=ft.FontWeight.W_500,
                    ),
                    ft.Text(
                        t("log_reduction_stat", pct=reduction_pct),
                        size=12,
                        color=COLOR_SUCCESS,
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
                color=COLOR_SUBTEXT,
            ),
            actions_row,
            log_container,
        ]
    )

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.icons.ASSESSMENT, color=COLOR_PRIMARY),
                ft.Text(
                    t("log_dialog_title"),
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=COLOR_TEXT,
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
        actions=[
            ft.ElevatedButton(
                t("btn_ok"),
                bgcolor=COLOR_PRIMARY,
                color=COLOR_TEXT,
                on_click=close_dialog,
            )
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    page.dialog = dialog
    dialog.open = True
    page.update()