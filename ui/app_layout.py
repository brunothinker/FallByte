import logging
import webbrowser
from pathlib import Path

import flet as ft

from ui.components.language_dialog import build_language_modal
from ui.components.neon_brand_text import build_neon_brand_title
from ui.components.theme_dialog import build_theme_modal
from ui.i18n import t
from ui.registry import MODULE_REGISTRY, resolve_active_module_id, resolve_parent_route
from ui.router import build_page_view
from ui.theme import get_color

logger = logging.getLogger(__name__)


def remove_stale_filepickers(page: ft.Page) -> None:
    """Drops FilePicker controls left in the overlay by a previous view."""
    page.overlay[:] = [
        ctrl for ctrl in page.overlay if not isinstance(ctrl, ft.FilePicker)
    ]


def _extract_submodules(module_def: object) -> list[dict]:
    """Extracts submodule entries from options, submodules, or tools."""
    for attr in ("options", "submodules", "tools"):
        raw = getattr(module_def, attr, None)
        if raw:
            break
    else:
        return []

    submodules: list[dict] = []
    for item in raw:
        if isinstance(item, dict):
            route = str(item.get("route_key") or item.get("route") or "")
            title_key = str(item.get("title_key") or "")
            icon = item.get("icon") or item.get(
                "sidebar_icon", ft.icons.SUBDIRECTORY_ARROW_RIGHT
            )
        else:
            route = str(
                getattr(item, "route_key", None) or getattr(item, "route", "") or ""
            )
            title_key = str(getattr(item, "title_key", "") or "")
            icon = getattr(item, "icon", None) or getattr(
                item, "sidebar_icon", ft.icons.SUBDIRECTORY_ARROW_RIGHT
            )
        if route and title_key:
            submodules.append({"route": route, "title_key": title_key, "icon": icon})
    return submodules


def create_app_layout(
    page: ft.Page, selected_paths: dict[str, Path], app_version: str = "dev"
) -> ft.Container:
    """Creates main application frame with sidebar, scrollable view, pinned back bar, and Esc."""
    current_route: str = "home"
    expanded_modules: set[str] = set()

    content_area = ft.Container(
        expand=True,
        padding=ft.padding.only(left=28, right=28, top=20, bottom=8),
        alignment=ft.alignment.center,
        bgcolor=get_color("background"),
    )

    modal_overlay = ft.Container(
        expand=True,
        visible=False,
        bgcolor=ft.colors.with_opacity(0.55, ft.colors.BLACK),
        alignment=ft.alignment.center,
        padding=20,
        on_click=lambda _: close_modal(),
    )

    def close_modal() -> None:
        if page.session.get("is_processing"):
            return
        modal_overlay.visible = False
        modal_overlay.content = None
        if modal_overlay.page:
            modal_overlay.update()

    def on_preferences_applied() -> None:
        modal_overlay.visible = False
        modal_overlay.content = None
        page.update()
        update_sidebar_labels()
        update_sidebar_active_states()
        update_view()

    def cleanup_page_overlays() -> None:
        if isinstance(page.dialog, ft.AlertDialog):
            page.dialog.open = False
        page.dialog = None
        page.overlay.clear()
        modal_overlay.visible = False
        modal_overlay.content = None

    def _sync_expanded_for_route(route: str) -> None:
        """Keeps only the active module expanded, collapsing any previously open module."""
        active_module = resolve_active_module_id(route)
        expanded_modules.clear()
        if active_module and active_module != "home":
            expanded_modules.add(active_module)

    def navigate_to(target_route: str) -> None:
        nonlocal current_route
        if page.session.get("is_processing"):
            return
        current_route = target_route
        _sync_expanded_for_route(current_route)
        update_sidebar_active_states()
        cleanup_page_overlays()
        update_view()

    def go_back() -> None:
        """Navigates deterministically one level up in the route hierarchy."""
        if page.session.get("is_processing"):
            return
        parent_route = resolve_parent_route(current_route)
        if parent_route:
            navigate_to(parent_route)

    def on_keyboard_event(e: ft.KeyboardEvent) -> None:
        """Handles Escape to close active modal or navigate up one hierarchy level."""
        if e.key != "Escape":
            return
        if page.session.get("is_processing"):
            return
        if modal_overlay.visible:
            close_modal()
            return
        go_back()

    page.on_keyboard_event = on_keyboard_event

    # Fixed bottom back bar outside the scrollable content_area
    btn_back = ft.ElevatedButton(
        text=t("header_back_tooltip"),
        icon=ft.icons.ARROW_BACK,
        bgcolor=get_color("card_bg"),
        color=get_color("text"),
        icon_color=get_color("primary"),
        on_click=lambda _: go_back(),
    )
    bottom_back_bar = ft.Container(
        content=btn_back,
        padding=ft.padding.only(top=8, bottom=18),
        alignment=ft.alignment.center,
        bgcolor=get_color("background"),
        visible=False,
    )

    def _sync_back_button_state() -> None:
        parent_route = resolve_parent_route(current_route)
        can_go_back = parent_route is not None and not bool(
            page.session.get("is_processing")
        )
        btn_back.text = t("header_back_tooltip")
        btn_back.bgcolor = get_color("card_bg")
        btn_back.color = get_color("text")
        btn_back.icon_color = get_color("primary")
        bottom_back_bar.bgcolor = get_color("background")
        bottom_back_bar.visible = can_go_back
        page.session.set("back_row", bottom_back_bar if can_go_back else None)

    def update_view() -> None:
        remove_stale_filepickers(page)
        view_control = build_page_view(
            route_key=current_route,
            page=page,
            selected_paths=selected_paths,
            on_navigate=navigate_to,
        )
        if isinstance(view_control, ft.Control):
            view_control.expand = False

        _sync_back_button_state()

        page.bgcolor = get_color("background")
        content_area.bgcolor = get_color("background")
        content_area.content = ft.Column(
            controls=[view_control],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        page.update()

    def open_theme_dialog() -> None:
        if page.session.get("is_processing"):
            return
        modal_overlay.content = build_theme_modal(
            page=page, on_close=close_modal, on_applied=on_preferences_applied
        )
        modal_overlay.visible = True
        page.update()

    def open_language_dialog() -> None:
        if page.session.get("is_processing"):
            return
        modal_overlay.content = build_language_modal(
            page=page, on_close=close_modal, on_applied=on_preferences_applied
        )
        modal_overlay.visible = True
        page.update()

    brand_container = ft.Container(
        content=build_neon_brand_title(
            value="FallByte",
            size=20,
        ),
        padding=ft.padding.symmetric(vertical=20),
    )

    nav_items_data = [
        {
            "id": "home",
            "route": "home",
            "title_key": "nav_home",
            "icon": ft.icons.HOME_OUTLINED,
            "submodules": [],
        }
    ] + [
        {
            "id": mod.id,
            "route": mod.route_key,
            "title_key": mod.title_key,
            "icon": mod.sidebar_icon,
            "submodules": _extract_submodules(mod),
        }
        for mod in MODULE_REGISTRY
    ]

    sidebar_groups: list[ft.Control] = []
    module_buttons: list[ft.Container] = []
    submodule_buttons: list[ft.Container] = []
    submodule_containers: dict[str, ft.Column] = {}

    def is_module_selected(module_id: str, module_route: str) -> bool:
        active_module = resolve_active_module_id(current_route)
        return current_route == module_route or active_module == module_id

    def build_sub_nav_button(module_id: str, sub: dict) -> ft.Container:
        sub_route = sub["route"]
        is_active = current_route == sub_route
        sub_icon = ft.Icon(
            sub["icon"],
            size=15,
            color=get_color("primary") if is_active else get_color("subtext"),
        )
        sub_text = ft.Text(
            t(sub["title_key"]),
            size=12,
            color=get_color("text") if is_active else get_color("subtext"),
            weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.NORMAL,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
            expand=True,
        )

        def on_sub_hover(e: ft.ControlEvent) -> None:
            active_now = current_route == sub_route
            e.control.bgcolor = (
                get_color("card_hover")
                if e.data == "true" or active_now
                else ft.colors.TRANSPARENT
            )
            e.control.update()

        btn = ft.Container(
            content=ft.Row(
                [sub_icon, sub_text],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=34, right=12, top=7, bottom=7),
            border_radius=8,
            bgcolor=get_color("card_hover") if is_active else ft.colors.TRANSPARENT,
            ink=True,
            tooltip=None,
            on_click=lambda _, r=sub_route: navigate_to(r),
            on_hover=on_sub_hover,
        )
        btn.data = {
            "module_id": module_id,
            "route": sub_route,
            "title_key": sub["title_key"],
            "icon_control": sub_icon,
            "text_control": sub_text,
        }
        submodule_buttons.append(btn)
        return btn

    def toggle_module_expand(module_id: str, module_route: str) -> None:
        if page.session.get("is_processing"):
            return
        if current_route == module_route and module_id in expanded_modules:
            expanded_modules.remove(module_id)
            update_sidebar_active_states()
            return
        navigate_to(module_route)

    def build_nav_group(data: dict) -> ft.Column:
        module_id = data["id"]
        route = data["route"]
        submodules: list[dict] = data["submodules"]
        has_submodules = len(submodules) > 0
        is_active = is_module_selected(module_id, route)
        is_expanded = module_id in expanded_modules

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
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
            expand=True,
        )
        chevron_control = ft.Icon(
            ft.icons.EXPAND_MORE if is_expanded else ft.icons.CHEVRON_RIGHT,
            size=16,
            color=get_color("subtext"),
            visible=has_submodules,
        )

        def on_mod_hover(e: ft.ControlEvent) -> None:
            active_now = is_module_selected(module_id, route)
            e.control.bgcolor = (
                get_color("card_hover")
                if e.data == "true" or active_now
                else ft.colors.TRANSPARENT
            )
            e.control.update()

        def on_mod_click(_: ft.ControlEvent) -> None:
            if has_submodules:
                toggle_module_expand(module_id, route)
            else:
                navigate_to(route)

        parent_btn = ft.Container(
            content=ft.Row(
                [icon_control, btn_text, chevron_control],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(vertical=10, horizontal=12),
            border_radius=8,
            bgcolor=get_color("card_hover") if is_active else ft.colors.TRANSPARENT,
            ink=True,
            tooltip=None,
            on_click=on_mod_click,
            on_hover=on_mod_hover,
        )
        parent_btn.data = {
            "id": module_id,
            "route": route,
            "title_key": data["title_key"],
            "icon_control": icon_control,
            "text_control": btn_text,
            "chevron_control": chevron_control,
            "has_submodules": has_submodules,
        }
        module_buttons.append(parent_btn)

        sub_controls: list[ft.Control] = [
            build_sub_nav_button(module_id, sub) for sub in submodules
        ]
        sub_column = ft.Column(
            controls=sub_controls,
            spacing=2,
            visible=has_submodules and is_expanded,
        )
        submodule_containers[module_id] = sub_column

        group_controls: list[ft.Control] = [parent_btn, sub_column]
        return ft.Column(controls=group_controls, spacing=2)

    for item in nav_items_data:
        sidebar_groups.append(build_nav_group(item))

    def update_sidebar_active_states() -> None:
        for btn in module_buttons:
            if isinstance(btn.data, dict):
                module_id = btn.data["id"]
                route = btn.data["route"]
                is_active = is_module_selected(module_id, route)
                is_expanded = module_id in expanded_modules
                is_direct_route = current_route == route

                btn.bgcolor = (
                    get_color("card_hover")
                    if is_direct_route
                    else (
                        ft.colors.with_opacity(0.45, get_color("card_hover"))
                        if is_active
                        else ft.colors.TRANSPARENT
                    )
                )

                icon_ctrl = btn.data["icon_control"]
                text_ctrl = btn.data["text_control"]
                chevron_ctrl = btn.data["chevron_control"]

                if isinstance(icon_ctrl, ft.Icon):
                    icon_ctrl.color = (
                        get_color("primary") if is_active else get_color("subtext")
                    )
                if isinstance(text_ctrl, ft.Text):
                    text_ctrl.color = (
                        get_color("text") if is_active else get_color("subtext")
                    )
                    text_ctrl.weight = (
                        ft.FontWeight.W_600 if is_active else ft.FontWeight.NORMAL
                    )
                if isinstance(chevron_ctrl, ft.Icon) and btn.data["has_submodules"]:
                    chevron_ctrl.name = (
                        ft.icons.EXPAND_MORE if is_expanded else ft.icons.CHEVRON_RIGHT
                    )
                    chevron_ctrl.color = (
                        get_color("primary") if is_active else get_color("subtext")
                    )

                if btn.page:
                    btn.update()

                sub_col = submodule_containers.get(module_id)
                if sub_col is not None:
                    sub_col.visible = btn.data["has_submodules"] and is_expanded
                    if sub_col.page:
                        sub_col.update()

        for sub_btn in submodule_buttons:
            if isinstance(sub_btn.data, dict):
                is_sub_active = current_route == sub_btn.data["route"]
                sub_btn.bgcolor = (
                    get_color("card_hover") if is_sub_active else ft.colors.TRANSPARENT
                )

                sub_icon = sub_btn.data["icon_control"]
                sub_text = sub_btn.data["text_control"]

                if isinstance(sub_icon, ft.Icon):
                    sub_icon.color = (
                        get_color("primary") if is_sub_active else get_color("subtext")
                    )
                if isinstance(sub_text, ft.Text):
                    sub_text.color = (
                        get_color("text") if is_sub_active else get_color("subtext")
                    )
                    sub_text.weight = (
                        ft.FontWeight.W_600 if is_sub_active else ft.FontWeight.NORMAL
                    )

                if sub_btn.page:
                    sub_btn.update()

    def update_sidebar_labels() -> None:
        brand_container.content = build_neon_brand_title(
            value="FallByte",
            size=20,
        )

        for btn in module_buttons:
            if isinstance(btn.data, dict):
                text_ctrl = btn.data["text_control"]
                if isinstance(text_ctrl, ft.Text):
                    text_ctrl.value = t(btn.data["title_key"])
                if btn.page:
                    btn.update()

        for sub_btn in submodule_buttons:
            if isinstance(sub_btn.data, dict):
                text_ctrl = sub_btn.data["text_control"]
                if isinstance(sub_btn.data["text_control"], ft.Text):
                    text_ctrl.value = t(sub_btn.data["title_key"])
                if sub_btn.page:
                    sub_btn.update()

        sidebar.bgcolor = get_color("sidebar_bg")
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

    lbl_theme_text = ft.Text(t("lbl_theme"), size=12, color=get_color("subtext"))
    lbl_lang_text = ft.Text(t("lbl_language"), size=12, color=get_color("subtext"))
    lbl_github_text = ft.Text(t("lbl_github_repo"), size=12, color=get_color("subtext"))

    icon_theme = ft.Icon(ft.icons.PALETTE_OUTLINED, size=18, color=get_color("primary"))
    icon_lang = ft.Icon(ft.icons.LANGUAGE, size=18, color=get_color("primary"))
    icon_github = ft.Icon(ft.icons.CODE, size=18, color=get_color("subtext"))

    def attach_footer_hover(container: ft.Container) -> ft.Container:
        container.on_hover = lambda e: (
            setattr(
                e.control,
                "bgcolor",
                get_color("card_hover")
                if e.data == "true"
                else ft.colors.TRANSPARENT,
            )
            or e.control.update()
        )
        return container

    btn_theme_menu = attach_footer_hover(
        ft.Container(
            content=ft.Row([icon_theme, lbl_theme_text], spacing=10),
            padding=ft.padding.symmetric(vertical=8, horizontal=12),
            border_radius=8,
            ink=True,
            tooltip=None,
            on_click=lambda _: open_theme_dialog(),
        )
    )
    btn_language_menu = attach_footer_hover(
        ft.Container(
            content=ft.Row([icon_lang, lbl_lang_text], spacing=10),
            padding=ft.padding.symmetric(vertical=8, horizontal=12),
            border_radius=8,
            ink=True,
            tooltip=None,
            on_click=lambda _: open_language_dialog(),
        )
    )
    btn_github_link = attach_footer_hover(
        ft.Container(
            content=ft.Row([icon_github, lbl_github_text], spacing=10),
            padding=ft.padding.symmetric(vertical=8, horizontal=12),
            border_radius=8,
            ink=True,
            tooltip=None,
            on_click=lambda _: webbrowser.open("https://github.com/brunothinker/FallByte"),
        )
    )

    footer_container = ft.Container(
        content=ft.Column(
            [btn_theme_menu, btn_language_menu, btn_github_link],
            spacing=2,
        ),
        padding=ft.padding.only(bottom=15),
    )

    sidebar_controls: list[ft.Control] = [
        brand_container,
        ft.Divider(height=1, color=ft.colors.OUTLINE_VARIANT),
        ft.Container(height=8),
        ft.Column(
            sidebar_groups,
            spacing=4,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        ),
        ft.Divider(height=1, color=ft.colors.OUTLINE_VARIANT),
        footer_container,
    ]

    sidebar = ft.Container(
        width=255,
        bgcolor=get_color("sidebar_bg"),
        padding=ft.padding.symmetric(horizontal=10),
        content=ft.Column(controls=sidebar_controls, expand=True),
    )

    lbl_version = ft.Text(
        f"v{app_version}",
        size=10,
        weight=ft.FontWeight.W_500,
        color=get_color("subtext"),
        right=12,
        bottom=8,
    )

    update_view()

    main_column = ft.Column(
        controls=[
            content_area,
            bottom_back_bar,
        ],
        expand=True,
        spacing=0,
    )

    content_stack = ft.Stack(
        [
            main_column,
            modal_overlay,
        ],
        expand=True,
    )

    return ft.Container(
        expand=True,
        content=ft.Stack(
            [
                ft.Row([sidebar, content_stack], expand=True, spacing=0),
                lbl_version,
            ],
            expand=True,
        ),
    )
