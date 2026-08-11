import logging
from typing import Any, Dict, List
import flet as ft

from ui.i18n import t
from ui.theme import (
    COLOR_ERROR,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_SUBTEXT,
    COLOR_TEXT,
)

# Setup module logger
logger = logging.getLogger(__name__)


def format_size(size_bytes: int) -> str:
    """Formats byte count into human-readable string representation (KB or MB)."""
    kb = size_bytes / 1024
    if kb >= 1024:
        return f"{kb / 1024:.2f} MB"
    return f"{kb:.1f} KB"


def show_summary_dialog(page: ft.Page, summary: Dict[str, Any]) -> None:
    """Displays modal dialog rendering execution metrics, file size stats, and detailed logs."""
    total = summary.get("total_files", summary.get("total", 0))
    success = summary.get("success", summary.get("successful", 0))
    failed = summary.get("failed", 0)
    elapsed = summary.get("elapsed_seconds", 0.0)
    errors = summary.get("errors", [])

    orig_bytes = summary.get("original_bytes", 0)
    comp_bytes = summary.get("compressed_bytes", 0)
    file_details: List[Dict[str, Any]] = summary.get("files", [])

    reduction_pct = 0.0
    if orig_bytes > 0:
        reduction_pct = ((orig_bytes - comp_bytes) / orig_bytes) * 100

    log_items: List[ft.Control] = []

    if file_details:
        for item in file_details:
            fname = item.get("name", "Unknown")
            item_orig = item.get("orig_bytes", 0)
            item_comp = item.get("comp_bytes", 0)
            item_success = item.get("success", True)
            item_err = item.get("error", "")

            if not item_success:
                log_items.append(
                    ft.Text(
                        f"[FAIL] {fname}: {item_err or t('msg_error')}",
                        size=11,
                        color=COLOR_ERROR,
                    )
                )
            else:
                item_pct = 0.0
                if item_orig > 0:
                    item_pct = ((item_orig - item_comp) / item_orig) * 100

                orig_str = format_size(item_orig)
                comp_str = format_size(item_comp)

                log_items.append(
                    ft.Text(
                        f"[OK] {fname:<25} | {orig_str} -> {comp_str} | -{item_pct:.1f}%",
                        size=11,
                        color=COLOR_SUCCESS,
                    )
                )
    elif errors:
        for err in errors:
            file_name = err.get("file", "Unknown")
            reason = err.get("error", "Unspecified error")
            log_items.append(
                ft.Text(
                    f"[ERROR] {file_name}: {reason}",
                    size=11,
                    color=COLOR_ERROR,
                )
            )
    else:
        log_items.append(
            ft.Text(f"[OK] {t('log_no_errors')}", size=11, color=COLOR_SUCCESS)
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
                    log_items, scroll=ft.ScrollMode.AUTO, spacing=4
                ),
                bgcolor=ft.colors.BLACK12,
                padding=10,
                border_radius=8,
                height=150,
            ),
        ],
        visible=False,
        spacing=8,
    )

    def toggle_logs(e: ft.ControlEvent) -> None:
        """Toggles detail log container visibility."""
        log_container.visible = not log_container.visible
        btn_toggle_log.text = (
            t("log_btn_hide_logs")
            if log_container.visible
            else t("log_btn_view_logs")
        )
        dialog.update()

    btn_toggle_log = ft.TextButton(
        text=t("log_btn_view_logs"),
        icon=ft.icons.LIST_ALT,
        on_click=toggle_logs,
    )

    def close_dialog(e: ft.ControlEvent) -> None:
        """Closes summary dialog modal."""
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
            btn_toggle_log,
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