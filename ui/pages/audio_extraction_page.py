from collections.abc import Callable, Mapping
from typing import Any

import flet as ft

from ui.components.tool_page import ToolPageWidgets, build_tool_page
from ui.controllers.audio_extraction_controller import (
    AudioExtractionController,
    AudioExtractionOptions,
)
from ui.i18n import t
from ui.theme import get_color
from ui.utils.format_utils import audio_output_formats, video_input_formats

ROUTE_KEY = "audio_extraction"


def _parse_stream_index(raw: Any) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def create_audio_extraction_page(
    page: ft.Page,
    selected_paths: dict[str, Any],
    _on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds the single-file video-to-audio extraction page."""
    controller = AudioExtractionController()
    saved_opts = (selected_paths.get(ROUTE_KEY) or {}).get("options") or {}
    output_formats = audio_output_formats()
    initial_fmt = saved_opts.get("target_format")
    if initial_fmt not in output_formats:
        initial_fmt = output_formats[0]

    dd_format = ft.Dropdown(
        label=t("lbl_target_format"),
        value=initial_fmt,
        width=385,
        filled=True,
        bgcolor=get_color("card_bg"),
        fill_color=get_color("card_bg"),
        menu_style=ft.MenuStyle(
            bgcolor=get_color("card_bg"),
            side=ft.BorderSide(1, get_color("primary")),
        ),
        border_color=ft.Colors.with_opacity(0.45, get_color("primary")),
        border_width=1,
        focused_border_color=get_color("primary"),
        focused_border_width=1.5,
        options=[ft.dropdown.Option(fmt) for fmt in output_formats],
    )

    dd_track = ft.Dropdown(
        label=t("lbl_audio_track"),
        value=None,
        width=385,
        visible=False,
        filled=True,
        bgcolor=get_color("card_bg"),
        fill_color=get_color("card_bg"),
        menu_style=ft.MenuStyle(
            bgcolor=get_color("card_bg"),
            side=ft.BorderSide(1, get_color("primary")),
        ),
        border_color=ft.Colors.with_opacity(0.45, get_color("primary")),
        border_width=1,
        focused_border_color=get_color("primary"),
        focused_border_width=1.5,
        options=[],
    )

    def on_input_selected(e: ft.FilePickerResultEvent, w: ToolPageWidgets) -> None:
        controller.handle_source_selected(
            e=e,
            lbl_in_path=w.lbl_in_path,
            lbl_status=w.lbl_status,
            dd_track=dd_track,
        )

    def on_restore_state(opts: Mapping[str, Any], _w: ToolPageWidgets) -> None:
        controller.restore_track_selector(
            dd_track=dd_track,
            selected_stream_index=_parse_stream_index(opts.get("stream_index")),
        )

    def get_selected_stream_index() -> int | None:
        if not dd_track.visible:
            return None
        return _parse_stream_index(dd_track.value)

    return build_tool_page(
        page=page,
        controller=controller,
        title_key="audio_hub_card_extraction_title",
        formats=video_input_formats(),
        notice_key="msg_supported_formats_notice_tracks",
        source_mode="file",
        file_icon=ft.Icons.VIDEO_FILE,
        extra_controls=[dd_format, dd_track],
        get_params=lambda: AudioExtractionOptions(
            target_format=dd_format.value or output_formats[0],
            stream_index=get_selected_stream_index(),
        ),
        on_input_selected=on_input_selected,
        selected_paths=selected_paths,
        route_key=ROUTE_KEY,
        get_state=lambda: {
            "target_format": dd_format.value or output_formats[0],
            "stream_index": get_selected_stream_index(),
        },
        on_restore_state=on_restore_state,
    )
