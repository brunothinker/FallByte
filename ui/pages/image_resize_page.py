from collections.abc import Callable
from pathlib import Path

import flet as ft

from ui.components.io_picker_card import create_clickable_card
from ui.components.path_label import create_path_label
from ui.components.source_picker_card import create_source_picker_card
from ui.controllers.image_resize_controller import (
    ImageResizeController,
    ResizeOptions,
)
from ui.i18n import t
from ui.theme import (
    BUTTON_HEIGHT,
    FORM_WIDTH,
    get_color,
)
from ui.utils.format_utils import format_list, image_input_formats


def _parse_positive_int(raw: str | None) -> int | None:
    """Parses a stripped text field value into a positive integer or None."""
    if not raw or not raw.strip():
        return None
    try:
        value = int(raw.strip())
        return value if value > 0 else None
    except ValueError:
        return None


def create_image_resize_page(
    page: ft.Page,
    _selected_paths: dict[str, Path],
    on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds unified image resize page layout referencing i18n keys."""
    controller = ImageResizeController()

    lbl_in_path = create_path_label()
    lbl_out_path = create_path_label()
    lbl_status = ft.Text("", size=13, weight=ft.FontWeight.W_600)
    progress_bar = ft.ProgressBar(width=FORM_WIDTH, value=0, visible=False)

    dd_mode = ft.Dropdown(
        label=t("lbl_resize_mode"),
        value="dimension",
        width=385,
        options=[
            ft.dropdown.Option(key="dimension", text=t("resize_mode_dimension")),
            ft.dropdown.Option(key="percentage", text=t("resize_mode_percentage")),
        ],
    )

    txt_max_width = ft.TextField(
        label=t("lbl_max_width"),
        value="1920",
        width=185,
        suffix_text="px",
        keyboard_type=ft.KeyboardType.NUMBER,
    )

    txt_max_height = ft.TextField(
        label=t("lbl_max_height"),
        value="1080",
        width=185,
        suffix_text="px",
        keyboard_type=ft.KeyboardType.NUMBER,
    )

    dimension_row = ft.Row(
        [txt_max_width, txt_max_height],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=15,
        visible=True,
    )

    txt_percentage = ft.TextField(
        label=t("lbl_scale_percentage"),
        value="50",
        width=385,
        suffix_text="%",
        keyboard_type=ft.KeyboardType.NUMBER,
        visible=False,
    )

    def on_mode_change(_: ft.ControlEvent) -> None:
        is_dimension = (dd_mode.value or "dimension") == "dimension"
        dimension_row.visible = is_dimension
        txt_percentage.visible = not is_dimension
        page.update()

    dd_mode.on_change = on_mode_change

    allowed_exts = [f.lower() for f in image_input_formats()]

    picker_in_file = ft.FilePicker(
        on_result=lambda e: controller.handle_input_result(e, lbl_in_path, lbl_status)
    )
    picker_in_dir = ft.FilePicker(
        on_result=lambda e: controller.handle_input_result(e, lbl_in_path, lbl_status)
    )
    picker_out = ft.FilePicker(
        on_result=lambda e: controller.handle_output_result(e, lbl_out_path, lbl_status)
    )

    for p in (picker_in_file, picker_in_dir, picker_out):
        if p not in page.overlay:
            page.overlay.append(p)

    card_in = create_source_picker_card(
        lbl_in_path=lbl_in_path,
        on_select_file=lambda: controller.open_picker(
            picker_in_file, allow_directory=False, allowed_extensions=allowed_exts
        ),
        on_select_folder=lambda: controller.open_picker(
            picker_in_dir, allow_directory=True
        ),
        file_icon=ft.icons.UPLOAD_FILE,
    )

    card_out = create_clickable_card(
        title=t("lbl_destination"),
        icon=ft.icons.FOLDER,
        lbl_text=lbl_out_path,
        on_click_action=lambda _: controller.open_picker(
            picker_out, allow_directory=True, is_output=True
        ),
    )

    btn_action = ft.ElevatedButton(
        t("btn_process"),
        icon=ft.icons.PLAY_ARROW,
        bgcolor=get_color("primary"),
        color=get_color("text"),
        width=FORM_WIDTH,
        height=BUTTON_HEIGHT,
    )

    lbl_notice = ft.Text(
        t(
            "msg_supported_formats_notice_resize",
            formats=format_list(image_input_formats()),
        ),
        size=11,
        color=get_color("subtext"),
        text_align=ft.TextAlign.CENTER,
    )

    def _collect_options() -> ResizeOptions:
        mode = dd_mode.value or "dimension"
        if mode == "dimension":
            return ResizeOptions(
                mode=mode,
                max_width=_parse_positive_int(txt_max_width.value),
                max_height=_parse_positive_int(txt_max_height.value),
                percentage=None,
            )
        return ResizeOptions(
            mode=mode,
            max_width=None,
            max_height=None,
            percentage=_parse_positive_int(txt_percentage.value),
        )

    def on_action_click(_: ft.ControlEvent) -> None:
        """Handles action button clicks forwarding resize options to controller."""
        controller.handle_action_click(
            page=page,
            options=_collect_options(),
            lbl_status=lbl_status,
            progress_bar=progress_bar,
            btn_action=btn_action,
        )

    btn_action.on_click = on_action_click

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
                [
                    ft.Text(
                        t("image_hub_card_resize_title"),
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
                    dd_mode,
                    dimension_row,
                    txt_percentage,
                    ft.Container(height=5),
                    progress_bar,
                    btn_action,
                    lbl_notice,
                    lbl_status,
                ],
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ),
    )
