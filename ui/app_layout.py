import logging
import webbrowser
from pathlib import Path
from typing import Any

import flet as ft

from ui.components.language_dialog import build_language_modal
from ui.components.neon_brand_text import build_neon_brand_title
from ui.components.theme_dialog import build_theme_modal
from ui.i18n import t
from ui.registry import MODULE_REGISTRY, resolve_active_module_id, resolve_parent_route
from ui.router import build_page_view
from ui.theme import get_color

logger = logging.getLogger(__name__)


def _page_state(page: ft.Page) -> dict[str, Any]:
    """Returns a mutable per-page dictionary for UI state (processing lock, back bar)."""
    if not isinstance(getattr(page, "data", None), dict):
        page.data = {}
    return page.data


def remove_stale_filepickers(page: ft.Page) -> None:
    """Drops FilePicker controls/services left behind by a previous view."""
    overlay = getattr(page, "overlay", None)
    if isinstance(overlay, list):
        overlay[:] = [
            ctrl for ctrl in overlay if not isinstance(ctrl, ft.FilePicker)
        ]
    services = getattr(page, "services", None)
    if isinstance(services, list):
        services[:] = [
            srv for srv in services if not isinstance(srv, ft.FilePicker)
        ]


def _extract_submodules(module_def: object) -> list[dict]:
    """Extracts submodule entries from a module definition's options list."""
    options = getattr(module_def, "options", None) or []
    return [
        {
            "route": opt.route_key,
            "title_key": opt.title_key,
            "icon": opt.icon,
        }
        for opt in options
        if getattr(opt, "route_key", "") and getattr(opt, "title_key", "")
    ]


def _apply_nav_glow(
    container: ft.Container,
    *,
    is_current: bool = False,
    is_parent_active: bool = False,
    is_hovered: bool = False,
) -> None:
    """Applies consistent background, neon border, and outer glow to sidebar items."""
    primary = get_color("primary")
    highlighted = is_current or is_hovered
    if is_current or is_hovered:
        container.bgcolor = get_color("card_hover")
    elif is_parent_active:
        container.bgcolor = ft.Colors.with_opacity(0.45, get_color("card_hover"))
    else:
        container.bgcolor = ft.Colors.TRANSPARENT

    if highlighted:
        container.border = ft.Border.all(1.5, primary)
        container.shadow = ft.BoxShadow(
            blur_radius=12,
            spread_radius=1,
            color=ft.Colors.with_opacity(0.45, primary),
            blur_style=ft.BlurStyle.NORMAL,
        )
    elif is_parent_active:
        container.border = ft.Border.all(1.5, ft.Colors.with_opacity(0.45, primary))
        container.shadow = None
    else:
        container.border = ft.Border.all(1.5, ft.Colors.TRANSPARENT)
        container.shadow = None


def create_app_layout(
    page: ft.Page, selected_paths: dict[str, Path], app_version: str = "dev"
) -> ft.Container:
    """Creates main application frame with sidebar, scrollable view, pinned back bar, and Esc."""
    current_route: str = "home"
    expanded_modules: set[str] = set()
    state = _page_state(page)

    content_area = ft.Container(
        expand=True,
        padding=ft.Padding.only(left=28, right=28, top=20, bottom=8),
        alignment=ft.Alignment.CENTER,
        bgcolor=get_color("background"),
    )

    modal_overlay = ft.Container(
        expand=True,
        visible=False,
        bgcolor=ft.Colors.with_opacity(0.55, ft.Colors.BLACK),
        alignment=ft.Alignment.CENTER,
        padding=20,
        on_click=lambda _: close_modal(),
    )

    def close_modal() -> None:
        if state.get("is_processing"):
            return
        modal_overlay.visible = False
        modal_overlay.content = None
        try:
            if modal_overlay.page:
                modal_overlay.update()
        except RuntimeError:
            pass

    def on_preferences_applied() -> None:
        modal_overlay.visible = False
        modal_overlay.content = None
        page.update()
        update_sidebar_labels()
        update_sidebar_active_states()
        update_view()

    def cleanup_page_overlays() -> None:
        page.pop_dialog()
        page.overlay.clear()
        remove_stale_filepickers(page)
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
        if state.get("is_processing"):
            return
        current_route = target_route
        _sync_expanded_for_route(current_route)
        update_sidebar_active_states()
        cleanup_page_overlays()
        update_view()

    def go_back() -> None:
        """Navigates deterministically one level up in the route hierarchy."""
        if state.get("is_processing"):
            return
        parent_route = resolve_parent_route(current_route)
        if parent_route:
            navigate_to(parent_route)

    def on_keyboard_event(e: ft.KeyboardEvent) -> None:
        """Handles Escape to close active modal or navigate up one hierarchy level."""
        if e.key != "Escape":
            return
        if state.get("is_processing"):
            return
        if modal_overlay.visible:
            close_modal()
            return
        go_back()

    page.on_keyboard_event = on_keyboard_event

    # Fixed bottom back bar outside the scrollable content_area
    btn_back = ft.Button(
        content=t("header_back_tooltip"),
        icon=ft.Icons.ARROW_BACK,
        bgcolor=get_color("card_bg"),
        color=get_color("text"),
        icon_color=get_color("primary"),
        on_click=lambda _: go_back(),
    )
    bottom_back_bar = ft.Container(
        content=btn_back,
        padding=ft.Padding.only(top=8, bottom=18),
        alignment=ft.Alignment.CENTER,
        bgcolor=get_color("background"),
        visible=False,
    )

    def _sync_back_button_state() -> None:
        parent_route = resolve_parent_route(current_route)
        can_go_back = parent_route is not None and not bool(
            state.get("is_processing")
        )
        btn_back.content = t("header_back_tooltip")
        btn_back.bgcolor = get_color("card_bg")
        btn_back.color = get_color("text")
        btn_back.icon_color = get_color("primary")
        bottom_back_bar.bgcolor = get_color("background")
        bottom_back_bar.visible = can_go_back
        state["back_row"] = bottom_back_bar if can_go_back else None

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
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        page.update()

    def open_theme_dialog() -> None:
        if state.get("is_processing"):
            return
        modal_overlay.content = build_theme_modal(
            page=page, on_close=close_modal, on_applied=on_preferences_applied
        )
        modal_overlay.visible = True
        page.update()

    def open_language_dialog() -> None:
        if state.get("is_processing"):
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
        padding=ft.Padding.symmetric(vertical=20),
    )

    nav_items_data = [
        {
            "id": "home",
            "route": "home",
            "title_key": "nav_home",
            "icon": ft.Icons.HOME_OUTLINED,
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

        def on_sub_hover(e: Any) -> None:
            _apply_nav_glow(
                e.control,
                is_current=(current_route == sub_route),
                is_hovered=e.data in (True, "true"),
            )
            e.control.update()

        btn = ft.Container(
            content=ft.Row(
                [sub_icon, sub_text],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.only(left=34, right=12, top=7, bottom=7),
            border_radius=8,
            ink=True,
            tooltip=None,
            on_click=lambda _, r=sub_route: navigate_to(r),
            on_hover=on_sub_hover,
        )
        _apply_nav_glow(btn, is_current=is_active)
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
        if state.get("is_processing"):
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
            ft.Icons.EXPAND_MORE if is_expanded else ft.Icons.CHEVRON_RIGHT,
            size=16,
            color=get_color("subtext"),
            visible=has_submodules,
        )

        def on_mod_hover(e: Any) -> None:
            _apply_nav_glow(
                e.control,
                is_current=(current_route == route),
                is_parent_active=is_module_selected(module_id, route),
                is_hovered=e.data in (True, "true"),
            )
            e.control.update()

        def on_mod_click(_: Any) -> None:
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
            padding=ft.Padding.symmetric(vertical=10, horizontal=12),
            border_radius=8,
            ink=True,
            tooltip=None,
            on_click=on_mod_click,
            on_hover=on_mod_hover,
        )
        _apply_nav_glow(
            parent_btn,
            is_current=(current_route == route),
            is_parent_active=is_active,
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

                _apply_nav_glow(
                    btn,
                    is_current=is_direct_route,
                    is_parent_active=is_active,
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
                    chevron_ctrl.icon = (
                        ft.Icons.EXPAND_MORE if is_expanded else ft.Icons.CHEVRON_RIGHT
                    )
                    chevron_ctrl.color = (
                        get_color("primary") if is_active else get_color("subtext")
                    )

                try:
                    if btn.page:
                        btn.update()
                except RuntimeError:
                    pass

                sub_col = submodule_containers.get(module_id)
                if sub_col is not None:
                    sub_col.visible = btn.data["has_submodules"] and is_expanded
                    try:
                        if sub_col.page:
                            sub_col.update()
                    except RuntimeError:
                        pass

        for sub_btn in submodule_buttons:
            if isinstance(sub_btn.data, dict):
                is_sub_active = current_route == sub_btn.data["route"]
                _apply_nav_glow(sub_btn, is_current=is_sub_active)

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

                try:
                    if sub_btn.page:
                        sub_btn.update()
                except RuntimeError:
                    pass

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
                try:
                    if btn.page:
                        btn.update()
                except RuntimeError:
                    pass

        for sub_btn in submodule_buttons:
            if isinstance(sub_btn.data, dict):
                text_ctrl = sub_btn.data["text_control"]
                if isinstance(text_ctrl, ft.Text):
                    text_ctrl.value = t(sub_btn.data["title_key"])
                try:
                    if sub_btn.page:
                        sub_btn.update()
                except RuntimeError:
                    pass

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

        try:
            if sidebar.page:
                sidebar.update()
        except RuntimeError:
            pass

    lbl_theme_text = ft.Text(t("lbl_theme"), size=12, color=get_color("subtext"))
    lbl_lang_text = ft.Text(t("lbl_language"), size=12, color=get_color("subtext"))
    lbl_github_text = ft.Text(t("lbl_github_repo"), size=12, color=get_color("subtext"))

    icon_theme = ft.Icon(ft.Icons.PALETTE_OUTLINED, size=18, color=get_color("primary"))
    icon_lang = ft.Icon(ft.Icons.LANGUAGE, size=18, color=get_color("primary"))
    icon_github = ft.Icon(ft.Icons.CODE, size=18, color=get_color("subtext"))

    def attach_footer_hover(container: ft.Container) -> ft.Container:
        _apply_nav_glow(container)
        container.on_hover = lambda e: (
            _apply_nav_glow(e.control, is_hovered=e.data in (True, "true")),
            e.control.update(),
        )
        return container

    btn_theme_menu = attach_footer_hover(
        ft.Container(
            content=ft.Row([icon_theme, lbl_theme_text], spacing=10),
            padding=ft.Padding.symmetric(vertical=8, horizontal=12),
            border_radius=8,
            ink=True,
            tooltip=None,
            on_click=lambda _: open_theme_dialog(),
        )
    )
    btn_language_menu = attach_footer_hover(
        ft.Container(
            content=ft.Row([icon_lang, lbl_lang_text], spacing=10),
            padding=ft.Padding.symmetric(vertical=8, horizontal=12),
            border_radius=8,
            ink=True,
            tooltip=None,
            on_click=lambda _: open_language_dialog(),
        )
    )
    btn_github_link = attach_footer_hover(
        ft.Container(
            content=ft.Row([icon_github, lbl_github_text], spacing=10),
            padding=ft.Padding.symmetric(vertical=8, horizontal=12),
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
        padding=ft.Padding.only(bottom=15),
    )

    sidebar_controls: list[ft.Control] = [
        brand_container,
        ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
        ft.Container(height=8),
        ft.Column(
            sidebar_groups,
            spacing=4,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        ),
        ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
        footer_container,
    ]

    sidebar = ft.Container(
        width=255,
        bgcolor=get_color("sidebar_bg"),
        padding=ft.Padding.symmetric(horizontal=10),
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
