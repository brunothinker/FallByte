from pathlib import Path
from typing import Dict, List

import flet as ft
from ui.i18n import t
from ui.router import ROUTE_REGISTRY, build_page_view
from ui.theme import (
    COLOR_PRIMARY,
    COLOR_TEXT,
    COLOR_CARD_BG,
)


def create_app_layout(page: ft.Page, selected_paths: Dict[str, Path]) -> ft.Container:
    """
    Creates the main application frame containing a fixed header and content area.
    """
    navigation_stack: List[str] = ["home"]

    btn_back = ft.IconButton(
        icon=ft.icons.ARROW_BACK_IOS_NEW,
        icon_color=COLOR_PRIMARY,
        tooltip=t("header_back_tooltip"),
        visible=False,
        on_click=lambda _: go_back()
    )

    lbl_page_title = ft.Text(
        value="",
        size=18,
        weight="bold",
        color=COLOR_TEXT,
        text_align=ft.TextAlign.CENTER
    )

    content_area = ft.Container(expand=True)

    def cleanup_page_overlays():
        """
        SAFETY CLEANUP:
        Closes pending dialogs and clears FilePickers/Overlay from previous screens
        to prevent orphan windows when switching routes.
        """
        page.dialog = None
        page.overlay.clear()

    def update_header_and_content():
        # Clears overlays from previous screen before loading the new view!
        cleanup_page_overlays()

        current_route = navigation_stack[-1]
        route_info = ROUTE_REGISTRY.get(current_route, {})

        title_key = route_info.get("title_key", "default_header_title")
        lbl_page_title.value = t(title_key)
        btn_back.visible = len(navigation_stack) > 1

        content_area.content = build_page_view(
            route_key=current_route,
            page=page,
            selected_paths=selected_paths,
            on_navigate=navigate_to
        )

        page.update()

    def navigate_to(target_route: str):
        navigation_stack.append(target_route)
        update_header_and_content()

    def go_back():
        if len(navigation_stack) > 1:
            navigation_stack.pop()
            update_header_and_content()

    header_bar = ft.Container(
        height=55,
        padding=ft.padding.symmetric(horizontal=15),
        bgcolor=COLOR_CARD_BG,
        border_radius=8,
        content=ft.Row([
            ft.Container(content=btn_back, width=50, alignment=ft.alignment.center_left),
            ft.Container(content=lbl_page_title, expand=True, alignment=ft.alignment.center),
            ft.Container(width=50)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
    )

    update_header_and_content()

    return ft.Container(
        expand=True,
        padding=10,
        content=ft.Column([
            header_bar,
            ft.Container(height=5),
            content_area
        ], expand=True)
    )