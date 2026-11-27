"""UI controller tests for audio track selector visibility and selection."""

from pathlib import Path
from unittest.mock import MagicMock

import flet as ft

from src.utils.media_tracks import MediaTrack
from ui.controllers.audio_extraction_controller import (
    AudioExtractionController,
    AudioExtractionOptions,
)
from ui.pages.audio_extraction_page import create_audio_extraction_page


def _make_picker_event(path: Path) -> ft.FilePickerResultEvent:
    file_item = ft.FilePickerFile(id=0, name=path.name, size=10, path=str(path))
    return ft.FilePickerResultEvent(name="result", control=MagicMock(), files=[file_item])


def test_track_selector_shown_only_for_multi_track_single_file(tmp_path, monkeypatch):
    single_track_video = tmp_path / "single.mp4"
    single_track_video.write_bytes(b"123")
    multi_track_video = tmp_path / "multi.mkv"
    multi_track_video.write_bytes(b"123")
    batch_folder = tmp_path / "folder"
    batch_folder.mkdir()

    tracks_by_file = {
        single_track_video: [
            MediaTrack(stream_index=1, track_type="audio", codec="aac", language="eng", is_default=True)
        ],
        multi_track_video: [
            MediaTrack(stream_index=1, track_type="audio", codec="aac", language="eng", is_default=False),
            MediaTrack(stream_index=2, track_type="audio", codec="ac3", language="por", is_default=True),
        ],
    }

    monkeypatch.setattr(
        "ui.controllers.audio_extraction_controller.inspect_audio_tracks",
        lambda p: tracks_by_file.get(p, []),
    )

    ctrl = AudioExtractionController()
    lbl_in = MagicMock(spec=ft.Text)
    lbl_status = MagicMock(spec=ft.Text)
    dd_track = ft.Dropdown(visible=False)

    # 1. Single-track video -> hidden
    ctrl.handle_source_selected(_make_picker_event(single_track_video), lbl_in, lbl_status, dd_track)
    assert dd_track.visible is False
    assert dd_track.options == []

    # 2. Multi-track video -> visible, default track preselected
    ctrl.handle_source_selected(_make_picker_event(multi_track_video), lbl_in, lbl_status, dd_track)
    assert dd_track.visible is True
    assert len(dd_track.options) == 2
    assert dd_track.value == "2"

    # 3. Directory -> hidden again
    ctrl.handle_source_selected(_make_picker_event(batch_folder), lbl_in, lbl_status, dd_track)
    assert dd_track.visible is False
    assert dd_track.options == []


def test_audio_extraction_page_builds_and_passes_stream_index(tmp_path, monkeypatch):
    multi_video = tmp_path / "dual.mkv"
    multi_video.write_bytes(b"123")

    monkeypatch.setattr(
        "ui.controllers.audio_extraction_controller.inspect_audio_tracks",
        lambda _p: [
            MediaTrack(stream_index=1, track_type="audio", codec="aac", language="eng", is_default=True),
            MediaTrack(stream_index=4, track_type="audio", codec="dts", language="jpn", is_default=False),
        ],
    )

    page = MagicMock()
    page.data = {}
    selected_paths: dict = {}

    view = create_audio_extraction_page(page, selected_paths, lambda _: None)
    assert isinstance(view, ft.Container)

    # Simulate persisted state restoration
    selected_paths["audio_extraction"] = {
        "input_path": multi_video,
        "output_dir": tmp_path,
        "options": {"target_format": "FLAC", "stream_index": 4},
    }
    view_restored = create_audio_extraction_page(page, selected_paths, lambda _: None)
    assert isinstance(view_restored, ft.Container)
    assert AudioExtractionOptions(target_format="FLAC", stream_index=4).stream_index == 4
