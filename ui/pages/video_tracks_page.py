from collections.abc import Callable, Mapping
from typing import Any

import flet as ft

from ui.components.tool_page import ToolPageWidgets, build_tool_page
from ui.controllers.video_tracks_controller import VideoTracksController
from ui.i18n import t
from ui.theme import get_color
from ui.utils.format_utils import video_input_formats

ROUTE_KEY = "video_tracks"
TRACKS_BOX_WIDTH = 385


def _build_track_box(icon: ft.IconData, title_key: str, list_col: ft.Column) -> ft.Container:
    """Bordered box holding a titled checklist of tracks."""
    return ft.Container(
        width=TRACKS_BOX_WIDTH,
        padding=10,
        border=ft.Border.all(1, get_color("primary")),
        border_radius=10,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(icon, size=18, color=get_color("primary")),
                        ft.Text(
                            t(title_key),
                            size=13,
                            weight=ft.FontWeight.W_600,
                            color=get_color("text"),
                        ),
                    ],
                    spacing=6,
                ),
                list_col,
            ],
            spacing=4,
        ),
    )


def create_video_tracks_page(
    page: ft.Page,
    selected_paths: dict[str, Any],
    _on_navigate: Callable[[str], None],
) -> ft.Container:
    """Builds the single-file video audio & subtitle track selection page."""
    controller = VideoTracksController()

    audio_list_col = ft.Column(spacing=2, scroll=ft.ScrollMode.AUTO, height=78)
    subtitle_list_col = ft.Column(spacing=2, scroll=ft.ScrollMode.AUTO, height=78)

    tracks_container = ft.Column(
        [
            _build_track_box(ft.Icons.AUDIOTRACK, "lbl_audio_tracks", audio_list_col),
            _build_track_box(
                ft.Icons.SUBTITLES, "lbl_subtitle_tracks", subtitle_list_col
            ),
        ],
        visible=False,
        spacing=10,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    def on_input_selected(e: ft.FilePickerResultEvent, w: ToolPageWidgets) -> None:
        controller.handle_video_selected(
            e=e,
            lbl_in_path=w.lbl_in_path,
            lbl_status=w.lbl_status,
            tracks_container=tracks_container,
            audio_list_col=audio_list_col,
            subtitle_list_col=subtitle_list_col,
        )

    def on_restore_state(saved_opts: Mapping[str, Any], _w: ToolPageWidgets) -> None:
        raw_indices = saved_opts.get("selected_indices")
        indices = list(raw_indices) if isinstance(raw_indices, list) else None
        controller.restore_video_tracks(
            selected_indices=indices,
            tracks_container=tracks_container,
            audio_list_col=audio_list_col,
            subtitle_list_col=subtitle_list_col,
        )

    return build_tool_page(
        page=page,
        controller=controller,
        title_key="video_hub_card_tracks_title",
        formats=video_input_formats(),
        notice_key="msg_supported_formats_notice_tracks",
        source_mode="file",
        file_icon=ft.Icons.VIDEO_FILE,
        extra_controls=[tracks_container],
        get_params=controller.get_selected_stream_indices,
        on_input_selected=on_input_selected,
        trailing_spacer=False,
        control_width=TRACKS_BOX_WIDTH,
        spacing=10,
        scrollable=True,
        selected_paths=selected_paths,
        route_key=ROUTE_KEY,
        get_state=lambda: {
            "selected_indices": controller.get_selected_stream_indices()
        },
        on_restore_state=on_restore_state,
    )
