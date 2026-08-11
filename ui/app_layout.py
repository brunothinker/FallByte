import logging
from pathlib import Path
from typing import Dict, List
import flet as ft

from ui.i18n import t
from ui.router import ROUTE_REGISTRY, build_page_view
from ui.theme import COLOR_CARD_BG, COLOR_PRIMARY, COLOR_TEXT

# Setup module logger
logger = logging.getLogger(__name__)


def create_app_layout(
    page: ft.Page, selected_paths: Dict[str, Path]
) -> ft.Container:
    """Creates main application frame containing top header bar and scrollable centered view."""
    # Track route history for backward navigation
    navigation_stack: List[str] = ["home"]

    # Define top header navigation controls
    btn_back = ft.IconButton(
        icon=ft.icons.ARROW_BACK_IOS_NEW,
        icon_color=COLOR_PRIMARY,
        tooltip=t("header_back_tooltip"),
        visible=False,
        on_click=lambda _: go_back(),
    )

    lbl_page_title = ft.Text(
        value="",
        size=18,
        weight="bold",
        color=COLOR_TEXT,
        text_align=ft.TextAlign.CENTER,
    )

    # Dynamic scrollable view container filling remaining height
    content_area = ft.Container(expand=True, alignment=ft.alignment.center)

    def cleanup_page_overlays() -> None:
        """Closes pending alert dialogs and clears registered FilePicker overlays."""
        page.dialog = None
        page.overlay.clear()

    def update_header_and_content() -> None:
        """Clears overlays, updates header state, and renders active route view."""
        cleanup_page_overlays()

        current_route = navigation_stack[-1]
        route_info = ROUTE_REGISTRY.get(current_route, {})

        # Resolve header title based on active route key
        title_key = route_info.get("title_key", "default_header_title")
        lbl_page_title.value = t(title_key)
        btn_back.visible = len(navigation_stack) > 1

        # Render view control corresponding to current route
        view_control = build_page_view(
            route_key=current_route,
            page=page,
            selected_paths=selected_paths,
            on_navigate=navigate_to,
        )

        # Disable expand on page views to prevent zero-height bugs inside scrollable column
        if isinstance(view_control, ft.Control):
            view_control.expand = False

        # Wrap in scrollable column with vertical and horizontal centering
        content_area.content = ft.Column(
            controls=[view_control],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

        page.update()

    def navigate_to(target_route: str) -> None:
        """Pushes a new target route key onto the stack and triggers screen re-render."""
        navigation_stack.append(target_route)
        update_header_and_content()

    def go_back() -> None:
        """Pops active route from stack and returns to previous view."""
        if len(navigation_stack) > 1:
            navigation_stack.pop()
            update_header_and_content()

    # Build persistent top header bar
    header_bar = ft.Container(
        height=55,
        padding=ft.padding.symmetric(horizontal=15),
        bgcolor=COLOR_CARD_BG,
        border_radius=8,
        content=ft.Row(
            [
                ft.Container(
                    content=btn_back,
                    width=50,
                    alignment=ft.alignment.center_left,
                ),
                ft.Container(
                    content=lbl_page_title,
                    expand=True,
                    alignment=ft.alignment.center,
                ),
                ft.Container(width=50),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    # Initialize layout rendering
    update_header_and_content()

    # Return root responsive layout container
    return ft.Container(
        expand=True,
        padding=10,
        content=ft.Column(
            [header_bar, ft.Container(height=5), content_area], expand=True
        ),
    )