"""Scoped modal component for selecting the active Dark or Light application theme."""

import asyncio
from collections.abc import Callable

import flet as ft

from src.utils.config_manager import get_config_value, set_config_value
from ui.i18n import t
from ui.theme import (
    THEME_PRESETS,
    build_flet_theme,
    get_color,
    set_active_theme,
)


def build_theme_modal(
    page: ft.Page,
    on_close: Callable[[], None],
    on_applied: Callable[[], None],
) -> ft.Container:
    """Builds a compact 2-column (Dark / Light) theme selector modal card."""
    current_theme = str(get_config_value("theme", "blue_dark"))

    def select_theme(key: str) -> None:
        """Applies and persists the selected theme with progress feedback."""
        txt_title.value = t("lbl_theme")
        txt_processing.value = t("msg_processing")

        btn_close.disabled = True
        columns_row.visible = False
        progress_container.visible = True
        card.update()

        async def process_theme_change() -> None:
            await asyncio.sleep(0.35)
            set_active_theme(key)
            set_config_value("theme", key)

            page.theme = build_flet_theme()
            page.dark_theme = build_flet_theme()
            page.theme_mode = (
                ft.ThemeMode.LIGHT if key.endswith("_light") else ft.ThemeMode.DARK
            )
            on_applied()

        page.run_task(process_theme_change)

    def build_theme_tile(key: str) -> ft.Container:
        preset = THEME_PRESETS[key]
        swatch_primary = preset.get("primary", get_color("primary"))
        is_selected = key == current_theme

        return ft.Container(
            width=155,
            height=36,
            border_radius=8,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            bgcolor=(
                get_color("card_hover") if is_selected else get_color("background")
            ),
            border=ft.Border.all(
                1.5 if is_selected else 1,
                swatch_primary if is_selected else ft.Colors.OUTLINE_VARIANT,
            ),
            ink=True,
            on_click=lambda _, k=key: select_theme(k),
            content=ft.Row(
                [
                    # Left accent strip in the target theme's primary color
                    ft.Container(
                        width=7,
                        height=36,
                        bgcolor=swatch_primary,
                    ),
                    ft.Container(
                        expand=True,
                        padding=ft.Padding.symmetric(horizontal=10),
                        content=ft.Row(
                            [
                                ft.Text(
                                    t(f"theme_{key}"),
                                    size=13,
                                    weight=(
                                        ft.FontWeight.W_600
                                        if is_selected
                                        else ft.FontWeight.NORMAL
                                    ),
                                    color=get_color("text"),
                                    no_wrap=True,
                                ),
                                ft.Icon(
                                    ft.Icons.CHECK_CIRCLE,
                                    size=15,
                                    color=swatch_primary,
                                    visible=is_selected,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    dark_keys = [k for k in THEME_PRESETS if k.endswith("_dark")]
    light_keys = [k for k in THEME_PRESETS if k.endswith("_light")]

    dark_column = ft.Column(
        [
            ft.Row(
                [
                    ft.Icon(
                        ft.Icons.DARK_MODE_OUTLINED,
                        size=14,
                        color=get_color("subtext"),
                    ),
                    ft.Text(
                        t("theme_section_dark"),
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=get_color("subtext"),
                    ),
                ],
                spacing=6,
            ),
            *[build_theme_tile(k) for k in dark_keys],
        ],
        spacing=8,
        tight=True,
    )

    light_column = ft.Column(
        [
            ft.Row(
                [
                    ft.Icon(
                        ft.Icons.LIGHT_MODE_OUTLINED,
                        size=14,
                        color=get_color("subtext"),
                    ),
                    ft.Text(
                        t("theme_section_light"),
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=get_color("subtext"),
                    ),
                ],
                spacing=6,
            ),
            *[build_theme_tile(k) for k in light_keys],
        ],
        spacing=8,
        tight=True,
    )

    columns_row = ft.Row(
        [
            dark_column,
            ft.Container(
                width=1,
                height=225,
                bgcolor=ft.Colors.OUTLINE_VARIANT,
            ),
            light_column,
        ],
        spacing=12,
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.START,
        tight=True,
    )

    txt_title = ft.Text(
        t("lbl_select_theme"),
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
        width=376,
        bgcolor=get_color("card_bg"),
        border_radius=12,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
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
                                    ft.Icons.PALETTE_OUTLINED,
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
                columns_row,
                progress_container,
            ],
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )
    return card
