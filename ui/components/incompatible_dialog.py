
"""Confirmation dialog shown when a batch folder mixes supported and unsupported files."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import flet as ft

from ui.i18n import t
from ui.theme import get_color


def show_incompatible_files_dialog(
    page: ft.Page,
    unsupported_files: list[Path],
    supported_count: int,
    on_confirm: Callable[[], None],
) -> None:
    """Warns about unsupported files and lets the user continue with the compatible ones.

    Args:
        page: Active Flet Page instance to present the modal.
        unsupported_files: Files that will be skipped by the operation.
        supported_count: Number of compatible files that will be processed.
        on_confirm: Callback invoked after the dialog closes when the user proceeds.
    """
    ext_set = sorted({f.suffix.upper() for f in unsupported_files if f.suffix})
    sample_exts = ", ".join(ext_set[:4]) if ext_set else t("lbl_no_extension")

    def close_dialog(_: Any) -> None:
        dialog.open = False
        page.pop_dialog()
        page.update()

    def confirm_and_run(_: Any) -> None:
        dialog.open = False
        page.pop_dialog()
        page.update()
        on_confirm()

    dialog = ft.AlertDialog(
        modal=True,
        bgcolor=get_color("card_bg"),
        shape=ft.RoundedRectangleBorder(
            radius=12,
            side=ft.BorderSide(1, get_color("primary")),
        ),
        title=ft.Text(t("dialog_incompatible_title"), weight=ft.FontWeight.W_600),
        content=ft.Text(
            t(
                "dialog_incompatible_body",
                unsupported_count=len(unsupported_files),
                supported_count=supported_count,
                sample_exts=sample_exts,
            ),
            size=13,
        ),
        actions=list[ft.Control]([
            ft.TextButton(
                content=t("btn_cancel"),
                style=ft.ButtonStyle(color=get_color("subtext")),
                on_click=close_dialog,
            ),
            ft.Button(
                content=t("btn_continue"),
                bgcolor=get_color("primary"),
                color=get_color("text"),
                on_click=confirm_and_run,
            ),
        ]),
        actions_alignment=ft.MainAxisAlignment.END,
    )

    page.show_dialog(dialog)
