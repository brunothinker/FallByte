"""Scaffold builder shared by every tool page (conversion, compression, resize, ...).

It owns the labels, the file pickers, the source/destination cards, the progress
bar, the action button, the notice and the status label. Pages only provide
their tool-specific controls and a ``get_params`` callback.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import flet as ft

from ui.components.io_picker_card import create_clickable_card
from ui.components.path_label import create_path_label
from ui.components.source_picker_card import create_source_picker_card
from ui.controllers.base_controller import BaseController, JobUI
from ui.i18n import t
from ui.theme import BUTTON_HEIGHT, FORM_WIDTH, get_color
from ui.utils.format_utils import format_list

SourceMode = Literal["file_or_folder", "file", "folder"]


@dataclass(frozen=True)
class ToolPageWidgets:
    """Scaffold-owned controls handed to optional page hooks."""

    lbl_in_path: ft.Text
    lbl_out_path: ft.Text
    lbl_status: ft.Text
    progress_bar: ft.ProgressBar
    btn_action: ft.ElevatedButton


def build_tool_page(
    page: ft.Page,
    controller: BaseController,
    title_key: str,
    formats: list[str],
    *,
    notice_key: str = "msg_supported_formats_notice",
    source_mode: SourceMode = "file_or_folder",
    file_icon: str = ft.icons.UPLOAD_FILE,
    extra_controls: Sequence[ft.Control] = (),
    get_params: Callable[[], Any] = lambda: None,
    on_input_selected: Callable[[ft.FilePickerResultEvent, ToolPageWidgets], None]
    | None = None,
    trailing_spacer: bool = True,
    control_width: int = FORM_WIDTH,
    spacing: int = 12,
    scrollable: bool = False,
) -> ft.Container:
    """Builds the standard centered tool card and wires it to a controller.

    Args:
        page: Active Flet page (pickers are added to its overlay).
        controller: Controller exposing ``execute(ui, params)`` and picker handlers.
        title_key: i18n key of the card title.
        formats: Upper-case format names; used for the picker filter and the notice.
        notice_key: i18n key of the supported-formats notice (takes ``{formats}``).
        source_mode: ``"file_or_folder"`` (popup menu), ``"file"`` or ``"folder"`` only.
        file_icon: Icon used for file selection.
        extra_controls: Tool-specific controls rendered between the I/O row and the progress bar.
        get_params: Called on click; its result is forwarded to ``controller.execute``.
        on_input_selected: Optional replacement for the default input picker result handler.
        trailing_spacer: Adds a small spacer after ``extra_controls``.
        control_width: Width of the progress bar and the action button.
        spacing: Vertical spacing of the card column.
        scrollable: Makes the card column scroll when content overflows.

    Returns:
        ft.Container: The page view, ready to be returned by a ``create_*_page`` function.
    """
    lbl_in_path = create_path_label()
    lbl_out_path = create_path_label()
    lbl_status = ft.Text("", size=13, weight=ft.FontWeight.W_600)
    progress_bar = ft.ProgressBar(width=control_width, value=0, visible=False)

    btn_action = ft.ElevatedButton(
        t("btn_process"),
        icon=ft.icons.PLAY_ARROW,
        bgcolor=get_color("primary"),
        color=get_color("text"),
        width=control_width,
        height=BUTTON_HEIGHT,
    )

    widgets = ToolPageWidgets(
        lbl_in_path=lbl_in_path,
        lbl_out_path=lbl_out_path,
        lbl_status=lbl_status,
        progress_bar=progress_bar,
        btn_action=btn_action,
    )
    ui = JobUI(
        page=page,
        lbl_status=lbl_status,
        progress_bar=progress_bar,
        btn_action=btn_action,
    )

    def handle_input(e: ft.FilePickerResultEvent) -> None:
        if on_input_selected is not None:
            on_input_selected(e, widgets)
        else:
            controller.handle_input_result(e, lbl_in_path, lbl_status)

    picker_in_file = ft.FilePicker(on_result=handle_input)
    picker_in_dir = ft.FilePicker(on_result=handle_input)
    picker_out = ft.FilePicker(
        on_result=lambda e: controller.handle_output_result(e, lbl_out_path, lbl_status)
    )

    pickers = [picker_out]
    if source_mode in ("file_or_folder", "file"):
        pickers.insert(0, picker_in_file)
    if source_mode in ("file_or_folder", "folder"):
        pickers.insert(0, picker_in_dir)
    for picker in pickers:
        if picker not in page.overlay:
            page.overlay.append(picker)

    allowed_exts = [f.lower() for f in formats]

    def pick_file() -> None:
        controller.open_picker(
            picker_in_file, allow_directory=False, allowed_extensions=allowed_exts
        )

    def pick_folder() -> None:
        controller.open_picker(picker_in_dir, allow_directory=True)

    if source_mode == "file_or_folder":
        card_in = create_source_picker_card(
            lbl_in_path=lbl_in_path,
            on_select_file=pick_file,
            on_select_folder=pick_folder,
            file_icon=file_icon,
        )
    elif source_mode == "file":
        card_in = create_clickable_card(
            title=t("lbl_source"),
            icon=file_icon,
            lbl_text=lbl_in_path,
            on_click_action=lambda _: pick_file(),
        )
    else:
        card_in = create_clickable_card(
            title=t("lbl_source"),
            icon=ft.icons.FOLDER_OPEN,
            lbl_text=lbl_in_path,
            on_click_action=lambda _: pick_folder(),
        )

    card_out = create_clickable_card(
        title=t("lbl_destination"),
        icon=ft.icons.FOLDER,
        lbl_text=lbl_out_path,
        on_click_action=lambda _: controller.open_picker(
            picker_out, allow_directory=True, is_output=True
        ),
    )

    lbl_notice = ft.Text(
        t(notice_key, formats=format_list(formats)),
        size=11,
        color=get_color("subtext"),
        text_align=ft.TextAlign.CENTER,
    )

    btn_action.on_click = lambda _: controller.execute(ui, get_params())

    body: list[ft.Control] = [
        ft.Text(
            t(title_key),
            size=20,
            weight=ft.FontWeight.W_600,
            color=get_color("text"),
        ),
        ft.Divider(height=15, color=get_color("subtext")),
        ft.Row(
            [card_in, card_out],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=15,
            wrap=True,
        ),
        *extra_controls,
    ]
    if trailing_spacer:
        body.append(ft.Container(height=5))
    body.extend([progress_bar, btn_action, lbl_notice, lbl_status])

    return ft.Container(
        expand=True,
        alignment=ft.alignment.center,
        padding=20,
        content=ft.Container(
            width=FORM_WIDTH,
            padding=25,
            bgcolor=get_color("card_bg"),
            border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
            border_radius=12,
            content=ft.Column(
                body,
                spacing=spacing,
                scroll=ft.ScrollMode.AUTO if scrollable else None,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ),
    )
