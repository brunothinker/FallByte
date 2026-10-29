# app_layout.py
import logging
import threading
import time
import webbrowser
from pathlib import Path

import flet as ft

from src.utils.config_manager import set_config_value
from ui.i18n import AVAILABLE_LANGUAGES, TRANSLATIONS, set_language, t
from ui.router import build_page_view
from ui.theme import (
    THEME_PRESETS,
    build_flet_theme,
    get_color,
    set_active_theme,
)

# Setup module logger
logger = logging.getLogger(__name__)


def create_app_layout(
    page: ft.Page, selected_paths: dict[str, Path], app_version: str = "dev"
) -> ft.Container:
    """Creates main application frame with left sidebar navigation bar and history stack."""
    navigation_stack: list[str] = ["home"]

    # Dynamic main view container
    content_area = ft.Container(
        expand=True,
        padding=20,
        alignment=ft.alignment.center,
        bgcolor=get_color("background"),
    )

    def cleanup_page_overlays() -> None:
        """Closes pending alert dialogs and clears registered FilePicker overlays."""
        if isinstance(page.dialog, ft.AlertDialog):
            page.dialog.open = False
        page.dialog = None
        page.overlay.clear()

    def update_view() -> None:
        """Clears overlays and renders active route view with refreshed theme colors."""
        current_route = navigation_stack[-1]

        view_control = build_page_view(
            route_key=current_route,
            page=page,
            selected_paths=selected_paths,
            on_navigate=navigate_to,
        )

        if isinstance(view_control, ft.Control):
            view_control.expand = False

        # Back button styled with the active theme colors
        btn_back = ft.ElevatedButton(
            text=t("header_back_tooltip"),
            icon=ft.icons.ARROW_BACK,
            bgcolor=get_color("card_bg"),
            color=get_color("text"),
            icon_color=get_color("primary"),
            on_click=lambda _: go_back(),
            visible=len(navigation_stack) > 1,
        )

        page.bgcolor = get_color("background")
        content_area.bgcolor = get_color("background")
        content_area.content = ft.Column(
            controls=[
                view_control,
                ft.Container(
                    content=btn_back,
                    padding=ft.padding.only(top=20),
                    alignment=ft.alignment.center,
                ),
            ],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

        page.update()

    def navigate_to(target_route: str) -> None:
        """Pushes target route to stack and triggers view re-render."""
        if page.session.get("is_processing"):
            return
        if navigation_stack[-1] != target_route:
            navigation_stack.append(target_route)
        update_sidebar_active_states()
        cleanup_page_overlays()
        update_view()

    def go_back() -> None:
        """Pops active route from stack and returns to previous view."""
        if page.session.get("is_processing"):
            return
        if len(navigation_stack) > 1:
            navigation_stack.pop()
            update_sidebar_active_states()
            cleanup_page_overlays()
            update_view()

    def open_theme_dialog() -> None:
        """Opens a dialog with categorized Dark and Light presets, feedback progress, and persistence."""
        if page.session.get("is_processing"):
            return

        def select_theme(key: str) -> None:
            """Handles theme selection and displays progress feedback in the dialog."""
            txt_dialog_title.value = t("lbl_theme")
            txt_processing.value = t("msg_processing")

            theme_options_column.visible = False
            progress_container.visible = True
            theme_dialog.update()

            def process_theme_change() -> None:
                """Applies and persists the selected theme, then refreshes sidebar and view."""
                time.sleep(0.4)

                set_active_theme(key)
                set_config_value("theme", key)

                # Rebuild the Flet theme from the active preset
                page.theme = build_flet_theme()
                page.dark_theme = build_flet_theme()

                page.theme_mode = (
                    ft.ThemeMode.LIGHT
                    if key.endswith("_light")
                    else ft.ThemeMode.DARK
                )

                theme_dialog.open = False
                page.update()

                time.sleep(0.15)
                page.dialog = None

                update_sidebar_labels()
                update_sidebar_active_states()
                update_view()

            threading.Thread(target=process_theme_change, daemon=True).start()

        dark_keys = [k for k in THEME_PRESETS if k.endswith("_dark")]
        light_keys = [k for k in THEME_PRESETS if k.endswith("_light")]

        dark_buttons = [
            ft.TextButton(
                text=t(f"theme_{k}"),
                style=ft.ButtonStyle(color=get_color("text")),
                on_click=lambda _, key=k: select_theme(key),
            )
            for k in dark_keys
        ]

        light_buttons = [
            ft.TextButton(
                text=t(f"theme_{k}"),
                style=ft.ButtonStyle(color=get_color("text")),
                on_click=lambda _, key=k: select_theme(key),
            )
            for k in light_keys
        ]

        theme_options_column = ft.Column(
            [
                ft.Text(
                    t("theme_section_dark"),
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color=get_color("subtext"),
                ),
                *dark_buttons,
                ft.Divider(height=10, color=ft.colors.OUTLINE_VARIANT),
                ft.Text(
                    t("theme_section_light"),
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color=get_color("subtext"),
                ),
                *light_buttons,
            ],
            tight=True,
            spacing=2,
        )

        txt_dialog_title = ft.Text(
            t("lbl_select_theme"),
            size=16,
            weight=ft.FontWeight.BOLD,
            color=get_color("text"),
        )
        txt_processing = ft.Text(
            t("msg_processing"), size=13, color=get_color("subtext")
        )

        progress_container = ft.Column(
            [
                txt_processing,
                ft.ProgressBar(width=200, color=get_color("primary")),
            ],
            visible=False,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            tight=True,
        )

        theme_dialog = ft.AlertDialog(
            bgcolor=get_color("card_bg"),
            title=txt_dialog_title,
            content=ft.Container(
                content=ft.Column(
                    [
                        theme_options_column,
                        progress_container,
                    ],
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=10,
            ),
        )
        page.dialog = theme_dialog
        theme_dialog.open = True
        page.update()

    def open_language_dialog() -> None:
        """Opens a dialog listing the available languages with progress feedback and auto-close."""
        if page.session.get("is_processing"):
            return

        def select_language(code: str) -> None:
            """Handles language selection, displays progress bar, and closes dialog automatically."""
            target_translations = TRANSLATIONS.get(code, {})
            target_title = target_translations.get("lbl_language", t("lbl_language"))
            target_msg = target_translations.get("msg_processing", t("msg_processing"))

            txt_dialog_title.value = target_title
            txt_processing.value = target_msg

            lang_list_column.visible = False
            progress_container.visible = True
            language_dialog.update()

            def process_change() -> None:
                """Applies and persists the selected language, then refreshes sidebar and view."""
                time.sleep(0.4)

                set_language(code)
                set_config_value("language", code)
                page.title = t("app_title")

                language_dialog.open = False
                page.update()

                time.sleep(0.15)
                page.dialog = None

                update_sidebar_labels()
                update_view()

            threading.Thread(target=process_change, daemon=True).start()

        lang_list_column = ft.Column(
            [
                ft.TextButton(
                    text=label,
                    style=ft.ButtonStyle(color=get_color("text")),
                    on_click=lambda _, code=code: select_language(code),
                )
                for code, label in AVAILABLE_LANGUAGES.items()
            ],
            tight=True,
        )

        txt_dialog_title = ft.Text(
            t("lbl_language"),
            size=16,
            weight=ft.FontWeight.BOLD,
            color=get_color("text"),
        )
        txt_processing = ft.Text(
            t("msg_processing"), size=13, color=get_color("subtext")
        )

        progress_container = ft.Column(
            [
                txt_processing,
                ft.ProgressBar(width=200, color=get_color("primary")),
            ],
            visible=False,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            tight=True,
        )

        language_dialog = ft.AlertDialog(
            bgcolor=get_color("card_bg"),
            title=txt_dialog_title,
            content=ft.Container(
                content=ft.Column(
                    [
                        lang_list_column,
                        progress_container,
                    ],
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=10,
            ),
        )
        page.dialog = language_dialog
        language_dialog.open = True
        page.update()

    # Sidebar Header (Centered Brand Text)
    lbl_brand = ft.Text(
        "FallByte",
        size=20,
        weight=ft.FontWeight.BOLD,
        color=get_color("text"),
        text_align=ft.TextAlign.CENTER,
    )

    brand_container = ft.Container(
        content=ft.Row(
            [lbl_brand],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.padding.symmetric(vertical=20),
    )

    # Navigation items setup using i18n keys
    nav_items_data = [
        {"route": "home", "title_key": "nav_home", "icon": ft.icons.HOME_OUTLINED},
        {"route": "image_hub", "title_key": "image_hub_header_title", "icon": ft.icons.IMAGE_OUTLINED},
        {"route": "video_hub", "title_key": "video_hub_header_title", "icon": ft.icons.VIDEO_LIBRARY_OUTLINED},
    ]

    sidebar_buttons: list[ft.Control] = []

    def build_nav_button(data: dict) -> ft.Container:
        """Builds a sidebar navigation button with active-state styling."""
        route = data["route"]
        current_route = navigation_stack[-1]
        is_active = current_route == route or (
            route != "home" and current_route.startswith(route.split("_")[0])
        )

        icon_control = ft.Icon(
            data["icon"],
            size=20,
            color=get_color("primary") if is_active else get_color("subtext"),
        )

        btn_text = ft.Text(
            t(data["title_key"]),
            size=13,
            color=get_color("text") if is_active else get_color("subtext"),
            weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.NORMAL,
        )

        container = ft.Container(
            content=ft.Row(
                [
                    icon_control,
                    btn_text,
                ],
                spacing=12,
            ),
            padding=ft.padding.symmetric(vertical=10, horizontal=15),
            border_radius=8,
            bgcolor=get_color("card_hover") if is_active else ft.colors.TRANSPARENT,
            ink=True,
            tooltip=None,
            on_click=lambda _: navigate_to(route),
            on_hover=lambda e: setattr(
                e.control,
                "bgcolor",
                get_color("card_hover") if e.data == "true" or is_active else ft.colors.TRANSPARENT,
            )
            or e.control.update(),
        )
        container.data = {
            "route": route,
            "title_key": data["title_key"],
            "icon_control": icon_control,
            "text_control": btn_text,
        }
        return container

    for item in nav_items_data:
        sidebar_buttons.append(build_nav_button(item))

    def update_sidebar_active_states() -> None:
        """Refreshes sidebar button highlight colors according to the current route."""
        current_route = navigation_stack[-1]
        for btn in sidebar_buttons:
            if isinstance(btn, ft.Container) and isinstance(btn.data, dict):
                route = btn.data["route"]
                is_active = current_route == route or (
                    route != "home" and current_route.startswith(route.split("_")[0])
                )
                btn.bgcolor = get_color("card_hover") if is_active else ft.colors.TRANSPARENT

                icon_ctrl = btn.data["icon_control"]
                text_ctrl = btn.data["text_control"]

                if isinstance(icon_ctrl, ft.Icon):
                    icon_ctrl.color = get_color("primary") if is_active else get_color("subtext")
                if isinstance(text_ctrl, ft.Text):
                    text_ctrl.color = get_color("text") if is_active else get_color("subtext")
                    text_ctrl.weight = ft.FontWeight.W_600 if is_active else ft.FontWeight.NORMAL
                if btn.page:
                    btn.update()

    def update_sidebar_labels() -> None:
        """Refreshes sidebar texts and colors for the active language and theme."""
        for btn in sidebar_buttons:
            if isinstance(btn, ft.Container) and isinstance(btn.data, dict):
                text_ctrl = btn.data["text_control"]
                if isinstance(text_ctrl, ft.Text):
                    text_ctrl.value = t(btn.data["title_key"])
                if btn.page:
                    btn.update()

        sidebar.bgcolor = get_color("sidebar_bg")
        lbl_brand.color = get_color("text")
        lbl_version.color = get_color("subtext")
        lbl_theme_text.value = t("lbl_theme")
        lbl_theme_text.color = get_color("subtext")
        lbl_lang_text.value = t("lbl_language")
        lbl_lang_text.color = get_color("subtext")
        lbl_github_text.value = t("lbl_github_repo")
        lbl_github_text.color = get_color("subtext")

        icon_theme.color = get_color("primary")
        icon_lang.color = get_color("primary")
        icon_github.color = get_color("subtext")

        if sidebar.page:
            sidebar.update()

    # Footer Controls (Theme Selector, Language Selector & GitHub Repository link)
    lbl_theme_text = ft.Text(t("lbl_theme"), size=12, color=get_color("subtext"))
    lbl_lang_text = ft.Text(t("lbl_language"), size=12, color=get_color("subtext"))
    lbl_github_text = ft.Text(t("lbl_github_repo"), size=12, color=get_color("subtext"))

    icon_theme = ft.Icon(ft.icons.PALETTE_OUTLINED, size=18, color=get_color("primary"))
    icon_lang = ft.Icon(ft.icons.LANGUAGE, size=18, color=get_color("primary"))
    icon_github = ft.Icon(ft.icons.CODE, size=18, color=get_color("subtext"))

    btn_theme_menu = ft.Container(
        content=ft.Row(
            [
                icon_theme,
                lbl_theme_text,
            ],
            spacing=10,
        ),
        padding=ft.padding.symmetric(vertical=8, horizontal=15),
        border_radius=8,
        ink=True,
        tooltip=None,
        on_click=lambda _: open_theme_dialog(),
    )

    btn_language_menu = ft.Container(
        content=ft.Row(
            [
                icon_lang,
                lbl_lang_text,
            ],
            spacing=10,
        ),
        padding=ft.padding.symmetric(vertical=8, horizontal=15),
        border_radius=8,
        ink=True,
        tooltip=None,
        on_click=lambda _: open_language_dialog(),
    )

    btn_github_link = ft.Container(
        content=ft.Row(
            [
                icon_github,
                lbl_github_text,
            ],
            spacing=10,
        ),
        padding=ft.padding.symmetric(vertical=8, horizontal=15),
        border_radius=8,
        ink=True,
        tooltip=None,
        on_click=lambda _: webbrowser.open("https://github.com/brunothinker/FallByte"),
    )

    # Footer container stacking theme, language and GitHub buttons
    footer_container = ft.Container(
        content=ft.Column(
            [
                btn_theme_menu,
                btn_language_menu,
                btn_github_link,
            ],
            spacing=2,
        ),
        padding=ft.padding.only(bottom=15),
    )

    # Full Left Sidebar Assembly
    sidebar_controls: list[ft.Control] = [
        brand_container,
        ft.Divider(height=1, color=ft.colors.OUTLINE_VARIANT),
        ft.Container(height=10),
        ft.Column(sidebar_buttons, spacing=5, expand=True),
        ft.Divider(height=1, color=ft.colors.OUTLINE_VARIANT),
        footer_container,
    ]

    sidebar = ft.Container(
        width=230,
        bgcolor=get_color("sidebar_bg"),
        padding=ft.padding.symmetric(horizontal=10),
        content=ft.Column(
            controls=sidebar_controls,
            expand=True,
        ),
    )

    # Version label pinned softly at bottom-right corner without blocking pointer events
    lbl_version = ft.Text(
        f"v{app_version}",
        size=10,
        weight=ft.FontWeight.W_500,
        color=get_color("subtext"),
        right=10,
        bottom=8,
    )

    # Initialize view
    update_view()

    # Main root layout container
    return ft.Container(
        expand=True,
        content=ft.Stack(
            [
                ft.Row(
                    [
                        sidebar,
                        content_area,
                    ],
                    expand=True,
                    spacing=0,
                ),
                lbl_version,
            ],
            expand=True,
        ),
    )