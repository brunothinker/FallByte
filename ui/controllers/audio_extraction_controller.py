from dataclasses import dataclass
from pathlib import Path
from typing import Any

import flet as ft

from src.audio.audio_file_extraction import file_extractor, inspect_audio_tracks
from src.utils.file_result import FileResult
from src.utils.media_tracks import MediaTrack
from src.utils.output_naming import unique_extraction_output_path
from ui.controllers.base_controller import BaseController, ProgressCallback
from ui.i18n import t
from ui.theme import get_color
from ui.utils.format_utils import video_input_formats

__all__ = [
    "AudioExtractionController",
    "AudioExtractionOptions",
]


@dataclass(frozen=True)
class AudioExtractionOptions:
    """Validated user configuration for a single-file audio extraction execution."""

    target_format: str
    stream_index: int | None = None


def _resolve_params(params: Any) -> tuple[str, int | None]:
    """Normalizes either an AudioExtractionOptions or a raw format string."""
    if isinstance(params, AudioExtractionOptions):
        return params.target_format.lower(), params.stream_index
    return str(params).lower(), None


def _pick_default_track_index(tracks: list[MediaTrack]) -> int:
    """Returns the stream_index of the default track, falling back to the first track."""
    for track in tracks:
        if track.is_default:
            return track.stream_index
    return tracks[0].stream_index


def _safe_update(control: ft.Control | None) -> None:
    """Calls control.update() safely when the control is attached to a Flet Page."""
    if control is None:
        return
    try:
        if control.page:
            control.update()
    except RuntimeError:
        pass


class AudioExtractionController(BaseController):
    """Single-file audio extraction from videos. ``params`` is ``AudioExtractionOptions`` or format str."""

    progress_i18n_key = "msg_converting_progress"
    show_speed = True
    supports_batch_directory = False
    invalid_input_key = "msg_single_video_required"

    def __init__(self) -> None:
        super().__init__()
        self.audio_tracks: list[MediaTrack] = []

    def supported_formats(self) -> list[str]:
        return video_input_formats()

    def handle_source_selected(
        self,
        e: ft.FilePickerResultEvent,
        lbl_in_path: ft.Text,
        lbl_status: ft.Text,
        dd_track: ft.Dropdown,
    ) -> None:
        """Handles single video file selection and probes embedded audio tracks."""
        self.handle_input_result(e, lbl_in_path, lbl_status)
        self._refresh_track_selector(dd_track, lbl_status=lbl_status, preferred_index=None)

    def restore_track_selector(
        self,
        dd_track: ft.Dropdown,
        selected_stream_index: int | None = None,
    ) -> None:
        """Restores track selector options and value from persisted route state."""
        self._refresh_track_selector(
            dd_track, lbl_status=None, preferred_index=selected_stream_index
        )

    def _refresh_track_selector(
        self,
        dd_track: ft.Dropdown,
        lbl_status: ft.Text | None,
        preferred_index: int | None,
    ) -> None:
        if not self.selected_input or not self.selected_input.is_file():
            self.audio_tracks = []
            dd_track.options = []
            dd_track.value = None
            if dd_track.visible:
                dd_track.visible = False
                _safe_update(dd_track)
            return

        if lbl_status is not None:
            lbl_status.value = t("msg_inspecting_tracks")
            lbl_status.color = get_color("subtext")
            _safe_update(lbl_status)

        tracks = inspect_audio_tracks(self.selected_input)
        self.audio_tracks = tracks

        if len(tracks) > 1:
            valid_indices = {tr.stream_index for tr in tracks}
            chosen_idx = (
                preferred_index
                if preferred_index in valid_indices
                else _pick_default_track_index(tracks)
            )
            dd_track.options = [
                ft.dropdown.Option(
                    key=str(tr.stream_index),
                    text=tr.display_label(),
                )
                for tr in tracks
            ]
            dd_track.value = str(chosen_idx)
            dd_track.visible = True
        else:
            dd_track.options = []
            dd_track.value = None
            dd_track.visible = False

        _safe_update(dd_track)

        if lbl_status is not None:
            lbl_status.value = ""
            _safe_update(lbl_status)

    def build_output_path(self, input_path: Path, output_dir: Path, params: Any) -> Path:
        target_fmt, _ = _resolve_params(params)
        return unique_extraction_output_path(
            input_path=input_path,
            output_dir=output_dir,
            target_format=target_fmt,
        )

    def run_single_engine(
        self,
        input_path: Path,
        output_path: Path,
        params: Any,
        progress_cb: ProgressCallback,
    ) -> FileResult:
        target_fmt, stream_index = _resolve_params(params)
        return file_extractor(
            input_path=input_path,
            output_path=output_path,
            target_format=target_fmt,
            cancel_event=self.cancel_event,
            file_progress_callback=progress_cb,
            stream_index=stream_index,
        )
