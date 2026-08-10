from pathlib import Path
from typing import Callable, Dict
import flet as ft

from ui.controllers.images.conversion.conversion_controllers import (
    ConversionFileController,
    ConversionDirController,
)
from ui.i18n import t
from ui.theme import (
    COLOR_CARD_BG,
    COLOR_PRIMARY,
    COLOR_SUBTEXT,
    COLOR_TEXT,
    FORM_WIDTH,
    BUTTON_HEIGHT,
)
from ui.utils.conversion_utils import (
    SUPPORTED_CONVERSION_FORMATS,
    get_color_options,
)


def create_clickable_card(
    title: str,
    icon: str,
    lbl_text: ft.Text,
    on_click_action: Callable
) -> ft.Container:
    """
    Creates a responsive card container for direct file or directory selection.

    Args:
        title (str): Card title text displayed below the icon.
        icon (str): Flet icon name identifier.
        lbl_text (ft.Text): UI text component rendering the selection status or path.
        on_click_action (Callable): Callback function triggered when the card is clicked.

    Returns:
        ft.Container: Configured clickable card UI component.
    """
    return ft.Container(
        width=185,
        height=125,
        bgcolor=COLOR_CARD_BG,
        border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
        border_radius=12,
        padding=10,
        ink=True,
        on_click=on_click_action,
        content=ft.Column([
            ft.Icon(icon, size=28, color=COLOR_PRIMARY),
            ft.Text(title, size=12, weight=ft.FontWeight.W_600, color=COLOR_TEXT, text_align=ft.TextAlign.CENTER),
            lbl_text
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4)
    )


def create_conversion_file_page(
    page: ft.Page,
    selected_paths: Dict[str, Path],
    on_navigate: Callable[[str], None]
) -> ft.Container:
    """
    Builds the single-file image conversion page layout.

    Args:
        page (ft.Page): Current Flet window page instance.
        selected_paths (Dict[str, Path]): Context dictionary holding shared global paths.
        on_navigate (Callable[[str], None]): Navigation callback function for page routing.

    Returns:
        ft.Container: Main layout container for the single-file conversion UI.
    """
    controller = ConversionFileController()

    # Define text labels for selection paths and operation status
    lbl_file_path = ft.Text(t("lbl_not_selected"), size=11, color=COLOR_SUBTEXT, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1)
    lbl_out_path = ft.Text(t("lbl_not_selected"), size=11, color=COLOR_SUBTEXT, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1)
    lbl_status = ft.Text("", size=13, weight=ft.FontWeight.W_600)

    # Setup target format dropdown control
    dd_format = ft.Dropdown(
        label=t("lbl_target_format"),
        value=SUPPORTED_CONVERSION_FORMATS[0],
        width=385,
        options=[ft.dropdown.Option(fmt) for fmt in SUPPORTED_CONVERSION_FORMATS],
    )

    # Setup transparency replacement color dropdown control
    color_options = get_color_options()
    dd_color = ft.Dropdown(
        label=t("lbl_transparency_color"),
        value=color_options[0][0],
        width=385,
        options=[ft.dropdown.Option(key, text=label) for key, label in color_options],
    )

    # Initialize file and directory picker instances
    picker_file = ft.FilePicker(
        on_result=lambda e: controller.handle_file_result(e, lbl_file_path)
    )
    picker_dir = ft.FilePicker(
        on_result=lambda e: controller.handle_dir_result(e, lbl_out_path)
    )

    # Register pickers in page overlay if not present
    if picker_file not in page.overlay:
        page.overlay.append(picker_file)
    if picker_dir not in page.overlay:
        page.overlay.append(picker_dir)

    # Create selection cards for input file and output directory
    card_file = create_clickable_card(
        title=t("lbl_select_file"),
        icon=ft.icons.UPLOAD_FILE,
        lbl_text=lbl_file_path,
        on_click_action=lambda _: controller.open_file_picker(picker_file)
    )

    card_out = create_clickable_card(
        title=t("lbl_select_output_dir"),
        icon=ft.icons.FOLDER,
        lbl_text=lbl_out_path,
        on_click_action=lambda _: controller.open_dir_picker(picker_dir)
    )

    # Construct main view card container expanding to fill layout space
    return ft.Container(
        expand=True,
        alignment=ft.alignment.center,
        padding=20,
        content=ft.Container(
            width=FORM_WIDTH,
            padding=25,
            bgcolor=COLOR_CARD_BG,
            border_radius=12,
            content=ft.Column([
                ft.Text(t("form_conversion_file_title"), size=20, weight=ft.FontWeight.W_600, color=COLOR_TEXT),
                ft.Divider(height=15, color=COLOR_SUBTEXT),

                ft.Row(
                    [card_file, card_out],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=15,
                    wrap=True
                ),

                dd_format,
                dd_color,

                ft.Container(height=5),
                ft.ElevatedButton(
                    t("btn_process"),
                    icon=ft.icons.PLAY_ARROW,
                    bgcolor=COLOR_PRIMARY,
                    color=COLOR_TEXT,
                    on_click=lambda _: controller.execute_conversion(
                        page=page,
                        target_format=dd_format.value,
                        selected_color_key=dd_color.value,
                        lbl_status=lbl_status
                    ),
                    width=FORM_WIDTH,
                    height=BUTTON_HEIGHT
                ),
                lbl_status,
            ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )
    )


def create_conversion_dir_page(
    page: ft.Page,
    selected_paths: Dict[str, Path],
    on_navigate: Callable[[str], None]
) -> ft.Container:
    """
    Builds the batch directory image conversion page layout.

    Args:
        page (ft.Page): Current Flet window page instance.
        selected_paths (Dict[str, Path]): Context dictionary holding shared global paths.
        on_navigate (Callable[[str], None]): Navigation callback function for page routing.

    Returns:
        ft.Container: Main layout container for the batch directory conversion UI.
    """
    controller = ConversionDirController()

    # Define text labels and progress controls
    lbl_in_path = ft.Text(t("lbl_not_selected"), size=11, color=COLOR_SUBTEXT, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1)
    lbl_out_path = ft.Text(t("lbl_not_selected"), size=11, color=COLOR_SUBTEXT, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1)
    lbl_status = ft.Text("", size=13, weight=ft.FontWeight.W_600)
    progress_bar = ft.ProgressBar(width=FORM_WIDTH, value=0, visible=False)

    # Setup target format dropdown control
    dd_format = ft.Dropdown(
        label=t("lbl_target_format"),
        value=SUPPORTED_CONVERSION_FORMATS[0],
        width=385,
        options=[ft.dropdown.Option(fmt) for fmt in SUPPORTED_CONVERSION_FORMATS],
    )

    # Setup transparency replacement color dropdown control
    color_options = get_color_options()
    dd_color = ft.Dropdown(
        label=t("lbl_transparency_color"),
        value=color_options[0][0],
        width=385,
        options=[ft.dropdown.Option(key, text=label) for key, label in color_options],
    )

    # Initialize directory picker instances
    picker_in = ft.FilePicker(
        on_result=lambda e: controller.handle_in_dir_result(e, lbl_in_path)
    )
    picker_out = ft.FilePicker(
        on_result=lambda e: controller.handle_out_dir_result(e, lbl_out_path)
    )

    # Register pickers in page overlay if not present
    if picker_in not in page.overlay:
        page.overlay.append(picker_in)
    if picker_out not in page.overlay:
        page.overlay.append(picker_out)

    # Create selection cards for input and output directories
    card_in = create_clickable_card(
        title=t("lbl_select_input_dir"),
        icon=ft.icons.FOLDER_OPEN,
        lbl_text=lbl_in_path,
        on_click_action=lambda _: controller.open_dir_picker(picker_in)
    )

    card_out = create_clickable_card(
        title=t("lbl_select_output_dir"),
        icon=ft.icons.FOLDER,
        lbl_text=lbl_out_path,
        on_click_action=lambda _: controller.open_dir_picker(picker_out)
    )

    # Configure execution/cancellation action button
    btn_action = ft.ElevatedButton(
        t("btn_process"),
        icon=ft.icons.PLAY_ARROW,
        bgcolor=COLOR_PRIMARY,
        color=COLOR_TEXT,
        width=FORM_WIDTH,
        height=BUTTON_HEIGHT
    )

    btn_action.on_click = lambda _: controller.handle_action_click(
        page=page,
        target_format=dd_format.value,
        selected_color_key=dd_color.value,
        lbl_status=lbl_status,
        progress_bar=progress_bar,
        btn_action=btn_action
    )

    # Construct main view card container expanding to fill layout space
    return ft.Container(
        expand=True,
        alignment=ft.alignment.center,
        padding=20,
        content=ft.Container(
            width=FORM_WIDTH,
            padding=25,
            bgcolor=COLOR_CARD_BG,
            border_radius=12,
            content=ft.Column([
                ft.Text(t("form_conversion_dir_title"), size=20, weight=ft.FontWeight.W_600, color=COLOR_TEXT),
                ft.Divider(height=15, color=COLOR_SUBTEXT),

                ft.Row(
                    [card_in, card_out],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=15,
                    wrap=True
                ),

                dd_format,
                dd_color,

                ft.Container(height=5),
                progress_bar,
                btn_action,
                lbl_status,
            ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )
    )