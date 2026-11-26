"""Scoped modal component for selecting the active application language."""

import asyncio
from collections.abc import Callable

import flet as ft

from src.utils.config_manager import set_config_value
from ui import i18n
from ui.i18n import AVAILABLE_LANGUAGES, TRANSLATIONS, set_language, t
from ui.theme import get_color


def build_language_modal(
    page: ft.Page,
    on_close: Callable[[], None],
    on_applied: Callable[[], None],
) -> ft.Container:
    """Builds a compact 2-column language selector modal card."""

    def select_language(code: str) -> None:
        """Applies and persists the selected language with progress feedback."""
        target_translations = TRANSLATIONS.get(code, {})
        txt_title.value = target_translations.get("lbl_language", t("lbl_language"))
        txt_processing.value = target_translations.get(
            "msg_processing", t("msg_processing")
        )

        btn_close.disabled = True
        grid_container.visible = False
        progress_container.visible = True
        card.update()

        async def process_change() -> None:
            await asyncio.sleep(0.35)
            set_language(code)
            set_config_value("language", code)
            page.title = t("app_title")
            on_applied()

        page.run_task(process_change)

    def build_lang_tile(code: str, label: str) -> ft.Container:
        is_selected = code == i18n.CURRENT_LANG
        return ft.Container(
            width=160,
            padding=ft.Padding.symmetric(vertical=8, horizontal=12),
            border_radius=8,
            bgcolor=(
                get_color("card_hover") if is_selected else get_color("background")
            ),
            border=ft.Border.all(
                1.5 if is_selected else 1,
                get_color("primary") if is_selected else ft.Colors.OUTLINE_VARIANT,
            ),
            ink=True,
            on_click=lambda _, c=code: select_language(c),
            content=ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(
                                label,
                                size=13,
                                weight=(
                                    ft.FontWeight.W_600
                                    if is_selected
                                    else ft.FontWeight.NORMAL
                                ),
                                color=get_color("text"),
                                no_wrap=True,
                            ),
                            ft.Text(
                                code.upper(),
                                size=10,
                                color=(
                                    ft.Colors.OUTLINE_VARIANT
                                    if is_selected
                                    else get_color("subtext")
                                ),
                                weight=ft.FontWeight.BOLD,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE,
                        size=16,
                        color=get_color("primary"),
                        visible=is_selected,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    items = list(AVAILABLE_LANGUAGES.items())
    rows: list[ft.Control] = [
        ft.Row(
            [build_lang_tile(code, label) for code, label in items[idx : idx + 2]],
            spacing=10,
            alignment=ft.MainAxisAlignment.CENTER,
        )
        for idx in range(0, len(items), 2)
    ]

    grid_container = ft.Column(
        rows,
        spacing=8,
        tight=True,
    )

    txt_title = ft.Text(
        t("lbl_language"),
        size=15,
        weight=ft.FontWeight.BOLD,
        color=get_color("text"),
    )
    txt_processing = ft.Text(
        t("msg_processing"), size=13, color=get_color("subtext")
    )
    btn_close = ft.IconButton(
        icon=ft.Icons.CLOSE,
        icon_size=18,
        icon_color=get_color("subtext"),
        on_click=lambda _: on_close(),
    )

    progress_container = ft.Container(
        padding=ft.Padding.symmetric(vertical=24),
        visible=False,
        content=ft.Column(
            [
                txt_processing,
                ft.ProgressBar(width=200, color=get_color("primary")),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            tight=True,
        ),
    )

    card = ft.Container(
        width=372,
        bgcolor=get_color("card_bg"),
        border_radius=12,
        border=ft.Border.all(1, get_color("primary")),
        padding=20,
        shadow=ft.BoxShadow(
            spread_radius=1,
            blur_radius=24,
            color=ft.Colors.with_opacity(0.45, ft.Colors.BLACK),
            offset=ft.Offset(0, 8),
        ),
        on_click=lambda _: None,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Icon(
                                    ft.Icons.LANGUAGE,
                                    size=20,
                                    color=get_color("primary"),
                                ),
                                txt_title,
                            ],
                            spacing=8,
                        ),
                        btn_close,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=6),
                grid_container,
                progress_container,
            ],
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )
    return card
