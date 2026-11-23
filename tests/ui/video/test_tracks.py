"""Integration tests for `VideoTracksController`: track inspection, checkbox selection, and lossless remuxing."""

from unittest.mock import MagicMock, patch

import flet as ft

from src.video.utils.video_ffmpeg_utils import MediaTrack
from tests.ui.helpers import make_job_ui
from ui.controllers.video_tracks_controller import VideoTracksController
from ui.i18n import t


def test_video_tracks_inspection_populates_checkboxes_checked_by_default(
    tmp_workspace, monkeypatch
):
    """Selecting a video file inspects embedded tracks and renders pre-checked checkboxes."""
    in_dir, _ = tmp_workspace
    src_video = in_dir / "sample_video.mkv"
    src_video.write_bytes(b"video bytes")

    sample_audio = [
        MediaTrack(
            stream_index=1,
            track_type="audio",
            codec="opus",
            language="jpn",
            details="stereo",
            is_default=True,
        ),
        MediaTrack(
            stream_index=2,
            track_type="audio",
            codec="aac",
            language="por",
            details="stereo",
        ),
    ]
    sample_subs = [
        MediaTrack(
            stream_index=3,
            track_type="subtitle",
            codec="ass",
            language="por",
        ),
    ]

    monkeypatch.setattr(
        "ui.controllers.video_tracks_controller.inspect_video_tracks",
        lambda path: (sample_audio, sample_subs),
    )

    controller = VideoTracksController()
    lbl_in_path = MagicMock(spec=ft.Text)
    lbl_status = MagicMock(spec=ft.Text)
    tracks_container = MagicMock(spec=ft.Column)
    audio_list_col = MagicMock(spec=ft.Column, controls=[])
    subtitle_list_col = MagicMock(spec=ft.Column, controls=[])

    event = MagicMock()
    event.files = [MagicMock(path=str(src_video))]
    event.path = None
    controller.picker_active = True

    controller.handle_video_selected(
        e=event,
        lbl_in_path=lbl_in_path,
        lbl_status=lbl_status,
        tracks_container=tracks_container,
        audio_list_col=audio_list_col,
        subtitle_list_col=subtitle_list_col,
    )

    assert controller.selected_input == src_video
    assert controller.picker_active is False
    assert tracks_container.visible is True
    assert len(audio_list_col.controls) == 2
    assert len(subtitle_list_col.controls) == 1
    assert controller.get_selected_stream_indices() == [1, 2, 3], (
        "[ui] All embedded audio and subtitle tracks must start checked by default."
    )

    # Uncheck the subtitle track and the first audio track
    subtitle_list_col.controls[0].value = False
    audio_list_col.controls[0].value = False
    assert controller.get_selected_stream_indices() == [2], (
        "[ui] get_selected_stream_indices() must return only checked stream indices."
    )


def test_video_tracks_inspection_handles_video_without_subtitles_or_audio(
    tmp_workspace, monkeypatch
):
    """Displays translated empty-state placeholders when a video has no embedded audio/subtitle tracks."""
    in_dir, _ = tmp_workspace
    src_video = in_dir / "silent_clip.mp4"
    src_video.write_bytes(b"video bytes")

    monkeypatch.setattr(
        "ui.controllers.video_tracks_controller.inspect_video_tracks",
        lambda path: ([], []),
    )

    controller = VideoTracksController()
    lbl_in_path = MagicMock(spec=ft.Text)
    lbl_status = MagicMock(spec=ft.Text)
    tracks_container = MagicMock(spec=ft.Column)
    audio_list_col = MagicMock(spec=ft.Column, controls=[])
    subtitle_list_col = MagicMock(spec=ft.Column, controls=[])

    event = MagicMock()
    event.files = [MagicMock(path=str(src_video))]
    event.path = None

    controller.handle_video_selected(
        e=event,
        lbl_in_path=lbl_in_path,
        lbl_status=lbl_status,
        tracks_container=tracks_container,
        audio_list_col=audio_list_col,
        subtitle_list_col=subtitle_list_col,
    )

    assert tracks_container.visible is True
    assert len(audio_list_col.controls) == 1
    assert isinstance(audio_list_col.controls[0], ft.Text)
    assert audio_list_col.controls[0].value == t("msg_no_audio_tracks")

    assert len(subtitle_list_col.controls) == 1
    assert isinstance(subtitle_list_col.controls[0], ft.Text)
    assert subtitle_list_col.controls[0].value == t("msg_no_subtitle_tracks")
    assert controller.get_selected_stream_indices() == []


def test_video_tracks_rejects_directory_input(tmp_workspace, mock_page):
    """Ensures VideoTracksController refuses directory paths since track selection is single-file only."""
    in_dir, out_dir = tmp_workspace

    controller = VideoTracksController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    ui = make_job_ui(mock_page)

    controller.execute(ui, [])

    assert ui.lbl_status.value == t("msg_single_video_required"), (
        "[ui] VideoTracksController must display 'msg_single_video_required' when given a folder."
    )
    assert controller.is_processing is False


def test_video_tracks_execution_uses_unique_suffix_and_forwards_indices(
    tmp_workspace, mock_page, monkeypatch
):
    """Verifies single-file track remuxing forwards selected indices and avoids overwriting existing files."""
    in_dir, out_dir = tmp_workspace
    src_video = in_dir / "sample_video.mp4"
    src_video.write_bytes(b"source video data")

    preexisting = out_dir / "sample_video_tracks.mp4"
    preexisting.write_bytes(b"existing output")

    controller = VideoTracksController()
    controller.selected_input = src_video
    controller.selected_output_dir = out_dir

    ui = make_job_ui(mock_page)

    captured: dict = {}

    def fake_remux(
        input_path,
        output_path,
        selected_stream_indices,
        cancel_event=None,
        progress_callback=None,
    ):
        captured["input_path"] = input_path
        captured["output_path"] = output_path
        captured["indices"] = selected_stream_indices
        output_path.write_bytes(b"remuxed video data")
        return True

    monkeypatch.setattr(
        "ui.controllers.video_tracks_controller.remux_selected_tracks", fake_remux
    )

    with patch("ui.controllers.base_controller.show_summary_dialog") as mock_summary:
        controller._run_single_file_job(ui, [2])

        mock_summary.assert_called_once()
        payload = mock_summary.call_args[0][1]
        assert payload["success"] == 1
        assert payload["failed"] == 0

    assert captured["indices"] == [2], (
        f"[ui] Expected only checked stream index [2] to be forwarded, got {captured['indices']}."
    )
    assert preexisting.read_bytes() == b"existing output", (
        "[ui] VideoTracksController must never overwrite pre-existing files in the destination folder."
    )
    expected_new = out_dir / "sample_video_tracks_2.mp4"
    assert expected_new.exists()
    assert expected_new.read_bytes() == b"remuxed video data"
