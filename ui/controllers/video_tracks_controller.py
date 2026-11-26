from pathlib import Path
from typing import Any

import flet as ft

from src.utils.file_result import FileResult
from src.utils.output_naming import unique_tracks_output_path
from src.video.utils.video_ffmpeg_utils import MediaTrack
from src.video.video_track_selector import (
    inspect_video_tracks,
    remux_selected_tracks,
)
from ui.controllers.base_controller import BaseController, ProgressCallback
from ui.i18n import t
from ui.theme import get_color
from ui.utils.format_utils import video_input_formats

__all__ = ["VideoTracksController"]


class VideoTracksController(BaseController):
    """Single-file lossless remux. ``params`` is the list of selected stream indices."""

    progress_i18n_key = "msg_remuxing_progress"
    show_speed = True
    supports_batch_directory = False
    invalid_input_key = "msg_single_video_required"

    def __init__(self) -> None:
        """Initializes state variables for track selection and execution."""
        super().__init__()
        self.audio_tracks: list[MediaTrack] = []
        self.subtitle_tracks: list[MediaTrack] = []
        self._track_checkboxes: dict[int, ft.Checkbox] = {}

    def supported_formats(self) -> list[str]:
        return video_input_formats()

    # ------------------------------------------------------------------
    # Page hook: input selection inspects the embedded streams
    # ------------------------------------------------------------------

    def handle_video_selected(
        self,
        e: ft.FilePickerResultEvent,
        lbl_in_path: ft.Text,
        lbl_status: ft.Text,
        tracks_container: ft.Column,
        audio_list_col: ft.Column,
        subtitle_list_col: ft.Column,
    ) -> None:
        """Handles single video file selection, inspects embedded streams, and updates checklists."""
        self.handle_input_result(e, lbl_in_path, lbl_status)

        if not self.selected_input or not self.selected_input.is_file():
            self.audio_tracks = []
            self.subtitle_tracks = []
            self._track_checkboxes.clear()
            tracks_container.visible = False
            tracks_container.update()
            return

        lbl_status.value = t("msg_inspecting_tracks")
        lbl_status.color = get_color("subtext")
        lbl_status.update()

        audio_tracks, subtitle_tracks = inspect_video_tracks(self.selected_input)
        self.audio_tracks = audio_tracks
        self.subtitle_tracks = subtitle_tracks
        self._track_checkboxes.clear()

        self._populate_track_group(audio_list_col, audio_tracks, "msg_no_audio_tracks")
        self._populate_track_group(
            subtitle_list_col, subtitle_tracks, "msg_no_subtitle_tracks"
        )

        tracks_container.visible = True
        tracks_container.update()

        lbl_status.value = ""
        lbl_status.update()

    def _populate_track_group(
        self,
        target_col: ft.Column,
        tracks: list[MediaTrack],
        empty_key: str,
    ) -> None:
        """Rebuilds checkbox controls for a given track group or shows an empty placeholder."""
        target_col.controls.clear()

        if not tracks:
            target_col.controls.append(
                ft.Text(
                    t(empty_key),
                    size=12,
                    italic=True,
                    color=get_color("subtext"),
                )
            )
            return

        for track in tracks:
            cb = ft.Checkbox(
                label=track.display_label(),
                value=True,
                active_color=get_color("primary"),
                check_color="#FFFFFF",
            )
            self._track_checkboxes[track.stream_index] = cb
            target_col.controls.append(cb)

    def get_selected_stream_indices(self) -> list[int]:
        """Returns sorted stream indices for all currently checked audio and subtitle tracks."""
        return sorted(
            stream_idx for stream_idx, cb in self._track_checkboxes.items() if cb.value
        )

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_output_path(self, input_path: Path, output_dir: Path, params: Any) -> Path:
        """Non-colliding output path preserving the original container extension."""
        original_ext = input_path.suffix.lstrip(".").lower() or "mkv"
        return unique_tracks_output_path(
            input_path=input_path,
            output_dir=output_dir,
            target_format=original_ext,
        )

    def run_single_engine(
        self,
        input_path: Path,
        output_path: Path,
        params: Any,
        progress_cb: ProgressCallback,
    ) -> FileResult:
        def remux_progress(processed: float, fps: float, speed: float) -> None:
            # Remuxing has no known duration: the bar stays indeterminate.
            progress_cb(0.0, processed, fps, speed)

        return remux_selected_tracks(
            input_path=input_path,
            output_path=output_path,
            selected_stream_indices=list(params or []),
            cancel_event=self.cancel_event,
            progress_callback=remux_progress,
        )
