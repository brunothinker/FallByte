import logging
from typing import Dict, Any
import flet as ft

from ui.i18n import t
from ui.theme import (
    COLOR_CARD_BG,
    COLOR_ERROR,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_SUBTEXT,
    COLOR_TEXT,
)

# Setup module logger
logger = logging.getLogger(__name__)


def show_summary_dialog(page: ft.Page, summary: Dict[str, Any]) -> None:
    """
    Displays a modal dialog rendering conversion and compression metrics along with expandable logs.

    Args:
        page (ft.Page): Current Flet page instance where the modal dialog will be mounted.
        summary (Dict[str, Any]): Dictionary containing execution statistics such as total, success,
            failed counts, elapsed time, and detailed error messages.
    """
    # Extract execution metrics with fallbacks for key variations
    total = summary.get("total_files", summary.get("total", 0))
    success = summary.get("success", summary.get("successful", 0))
    failed = summary.get("failed", 0)
    elapsed = summary.get("elapsed_seconds", 0.0)
    errors = summary.get("errors", [])

    # Populate expandable log items list based on operation output
    log_items = []
    if errors:
        for err in errors:
            file_name = err.get("file", "Unknown")
            reason = err.get("error", "Unspecified error")
            log_items.append(
                ft.Text(f"[ERROR] {file_name}: {reason}", size=11, color=COLOR_ERROR)
            )
    else:
        log_items.append(
            ft.Text(f"[OK] {t('log_no_errors')}", size=11, color=COLOR_SUCCESS)
        )

    # Construct scrollable container holding log items
    log_container = ft.Column(
        controls=[
            ft.Text(t("log_detail_title"), size=12, weight=ft.FontWeight.BOLD, color=COLOR_TEXT),
            ft.Container(
                content=ft.Column(log_items, scroll=ft.ScrollMode.AUTO, spacing=4),
                bgcolor=ft.colors.BLACK12,
                padding=10,
                border_radius=8,
                height=150,
            )
        ],
        visible=False,
        spacing=8
    )

    def toggle_logs(e: ft.ControlEvent) -> None:
        """
        Toggles visibility of the detailed log container inside the dialog.

        Args:
            e (ft.ControlEvent): Event payload triggered by button click.
        """
        log_container.visible = not log_container.visible
        btn_toggle_log.text = t("log_btn_hide_logs") if log_container.visible else t("log_btn_view_logs")
        dialog.update()

    # Define button to expand or collapse detailed logs view
    btn_toggle_log = ft.TextButton(
        text=t("log_btn_view_logs"),
        icon=ft.icons.LIST_ALT,
        on_click=toggle_logs
    )

    def close_dialog(e: ft.ControlEvent) -> None:
        """
        Closes and unmounts the active alert dialog from page layout.

        Args:
            e (ft.ControlEvent): Event payload triggered by button click.
        """
        dialog.open = False
        page.update()

    # Build modal AlertDialog component holding statistics and toggleable logs
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row([
            ft.Icon(ft.icons.ASSESSMENT, color=COLOR_PRIMARY),
            ft.Text(t("log_dialog_title"), size=18, weight=ft.FontWeight.BOLD, color=COLOR_TEXT)
        ], spacing=10),
        content=ft.Container(
            width=400,
            content=ft.Column([
                ft.Row([
                    ft.Column([
                        ft.Text(t("log_summary_total"), size=11, color=COLOR_SUBTEXT),
                        ft.Text(str(total), size=16, weight=ft.FontWeight.BOLD, color=COLOR_TEXT),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Column([
                        ft.Text(t("log_summary_success"), size=11, color=COLOR_SUBTEXT),
                        ft.Text(str(success), size=16, weight=ft.FontWeight.BOLD, color=COLOR_SUCCESS),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Column([
                        ft.Text(t("log_summary_failed"), size=11, color=COLOR_SUBTEXT),
                        ft.Text(
                            str(failed),
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            color=COLOR_ERROR if failed > 0 else COLOR_TEXT
                        ),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                ], alignment=ft.MainAxisAlignment.SPACE_AROUND),

                ft.Divider(height=10, color=COLOR_SUBTEXT),
                ft.Text(f"{t('log_summary_time')}: {elapsed:.2f}s", size=12, color=COLOR_SUBTEXT),

                btn_toggle_log,
                log_container,
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=10, tight=True)
        ),
        actions=[
            ft.ElevatedButton("OK", bgcolor=COLOR_PRIMARY, color=COLOR_TEXT, on_click=close_dialog)
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    # Attach dialog to page and trigger layout rendering
    page.dialog = dialog
    dialog.open = True
    page.update()