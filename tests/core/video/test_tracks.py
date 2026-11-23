"""Unit tests for lossless video audio & subtitle track selection in `src.video.video_track_selector`."""

import logging
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.video import video_track_selector
from src.video.utils.video_ffmpeg_utils import (
    MediaTrack,
    StreamInfo,
    classify_subtitle_codec,
)
from src.video.video_track_selector import (
    build_track_selection_maps,
    inspect_video_tracks,
    remux_selected_tracks,
)


def _leftover_temp_files(directory: Path, stem: str) -> list[Path]:
    """Returns any temporary files left behind for `stem` in `directory`."""
    return list(directory.glob(f".{stem}_tmp_*"))


def test_build_track_selection_maps_deduplicates_and_sorts_indices():
    """Builds `-map 0:V?` followed by sorted, deduplicated `-map 0:<idx>` entries."""
    maps = build_track_selection_maps([4, 1, 4, 2, -1])

    assert maps == ["-map", "0:V?", "-map", "0:1", "-map", "0:2", "-map", "0:4"], (
        f"[video-tracks] Expected sorted deduplicated map args, got {maps}."
    )


def test_build_track_selection_maps_allows_empty_selection():
    """When all audio and subtitle tracks are unchecked, maps only the video stream (`0:V?`)."""
    maps = build_track_selection_maps([])

    assert maps == ["-map", "0:V?"], (
        f"[video-tracks] Empty track selection must map only video stream [' -map', '0:V?'], got {maps}."
    )


def test_inspect_video_tracks_returns_empty_for_missing_file(tmp_path):
    """Returns empty lists gracefully when the input file does not exist."""
    missing = tmp_path / "nonexistent.mkv"
    audio_tracks, subtitle_tracks = inspect_video_tracks(missing, ffmpeg_bin=Path("ffmpeg"))

    assert audio_tracks == []
    assert subtitle_tracks == []


def test_inspect_video_tracks_delegates_to_probe_media_tracks(tmp_path, monkeypatch):
    """Delegates probing of an existing video file to `probe_media_tracks`."""
    video_file = tmp_path / "movie.mkv"
    video_file.write_bytes(b"fake video bytes")

    expected_audio = [
        MediaTrack(stream_index=1, track_type="audio", codec="aac", language="por")
    ]
    expected_subs = [
        MediaTrack(stream_index=2, track_type="subtitle", codec="ass", language="eng")
    ]

    mock_probe = MagicMock(return_value=(expected_audio, expected_subs))
    monkeypatch.setattr(video_track_selector, "probe_media_tracks", mock_probe)

    audio_tracks, subtitle_tracks = inspect_video_tracks(
        video_file, ffmpeg_bin=Path("ffmpeg")
    )

    mock_probe.assert_called_once_with(Path("ffmpeg"), video_file)
    assert audio_tracks == expected_audio
    assert subtitle_tracks == expected_subs


def test_remux_selected_tracks_refuses_in_place_overwrite(tmp_path):
    """Refuses to overwrite the source file when input and output paths resolve identically."""
    video_file = tmp_path / "sample_video.mp4"
    video_file.write_bytes(b"original video")

    result = remux_selected_tracks(
        input_path=video_file,
        output_path=video_file,
        selected_stream_indices=[1],
        ffmpeg_bin=Path("ffmpeg"),
    )

    assert result is False, (
        "[video-tracks] remux_selected_tracks must refuse in-place overwrite of the source file."
    )
    assert video_file.read_bytes() == b"original video"


def test_remux_selected_tracks_raises_when_already_cancelled(tmp_path):
    """Raises `InterruptedError` immediately when `cancel_event` is pre-set."""
    src_file = tmp_path / "sample_video.mp4"
    src_file.write_bytes(b"original video")
    out_file = tmp_path / "sample_video_tracks.mp4"

    cancel_event = threading.Event()
    cancel_event.set()

    with pytest.raises(InterruptedError):
        remux_selected_tracks(
            input_path=src_file,
            output_path=out_file,
            selected_stream_indices=[1],
            cancel_event=cancel_event,
            ffmpeg_bin=Path("ffmpeg"),
        )


def test_remux_selected_tracks_builds_lossless_copy_commands_without_chapters(
    tmp_path, monkeypatch
):
    """Verifies lossless `-c copy`, `-map_chapters -1`, atomic temp target, and fallback strategies."""
    src_file = tmp_path / "sample_video.mp4"
    src_file.write_bytes(b"source mp4 bytes")
    out_file = tmp_path / "out" / "sample_video_tracks.mp4"

    monkeypatch.setattr(
        video_track_selector,
        "probe_streams",
        lambda *a, **kw: StreamInfo(video_codec="h264", duration_seconds=120.0),
    )
    monkeypatch.setattr(
        video_track_selector,
        "probe_media_tracks",
        lambda *a, **kw: ([], []),
    )

    captured: dict = {}

    def fake_run_strategies(
        strategies, output_path, display_name, cancel_event=None, progress_callback=None
    ):
        # Final destination must not exist yet while FFmpeg writes to the temp file.
        assert not out_file.exists(), (
            "[video-tracks] Destination file must not appear before strategies succeed."
        )
        assert output_path.parent == out_file.parent
        assert output_path.name.startswith(f".{out_file.stem}_tmp_")
        assert output_path.suffix == out_file.suffix

        captured["strategies"] = strategies
        captured["output_path"] = output_path
        captured["display_name"] = display_name
        output_path.write_bytes(b"remuxed mp4 bytes")
        if progress_callback:
            progress_callback(150.0, 0.0, 25.0)
        return strategies[0][0]

    monkeypatch.setattr(video_track_selector, "run_strategies", fake_run_strategies)

    progress_ticks: list[tuple[float, float, float]] = []
    ok = remux_selected_tracks(
        input_path=src_file,
        output_path=out_file,
        selected_stream_indices=[1],
        progress_callback=lambda sec, fps, spd: progress_ticks.append((sec, fps, spd)),
        ffmpeg_bin=Path("ffmpeg"),
    )

    assert ok is True
    assert out_file.exists() and out_file.read_bytes() == b"remuxed mp4 bytes"
    assert _leftover_temp_files(out_file.parent, out_file.stem) == []
    assert progress_ticks == [(120.0, 0.0, 25.0)], (
        f"[video-tracks] Progress callback must clamp processed seconds to duration (120.0s), got {progress_ticks}."
    )

    strategies = captured["strategies"]
    assert [label for label, _ in strategies] == [
        "lossless_remux_with_metadata",
        "lossless_remux_minimal",
        "lossless_remux_rescue",
    ]

    primary_cmd = strategies[0][1]
    assert "-c" in primary_cmd and primary_cmd[primary_cmd.index("-c") + 1] == "copy", (
        "[video-tracks] Primary remux command must use lossless stream copy (`-c copy`)."
    )
    assert (
        "-map_chapters" in primary_cmd
        and primary_cmd[primary_cmd.index("-map_chapters") + 1] == "-1"
    ), (
        "[video-tracks] Primary remux command must set `-map_chapters -1` so MP4 containers do not synthesize text chapter tracks."
    )
    assert "-map" in primary_cmd
    assert "0:V?" in primary_cmd
    assert "0:1" in primary_cmd
    assert "0:3" not in primary_cmd
    assert "-movflags" in primary_cmd and "+faststart" in primary_cmd
    assert primary_cmd[-1] == str(captured["output_path"])


def test_remux_selected_tracks_cleans_temp_file_and_preserves_existing_on_failure(
    tmp_path, monkeypatch
):
    """Removes the temp file on failure and leaves any pre-existing destination intact."""
    src_file = tmp_path / "source.mkv"
    src_file.write_bytes(b"source mkv bytes")
    out_file = tmp_path / "existing.mp4"
    out_file.write_bytes(b"intact existing output")

    monkeypatch.setattr(
        video_track_selector,
        "probe_streams",
        lambda *a, **kw: StreamInfo(video_codec="h264", duration_seconds=60.0),
    )
    monkeypatch.setattr(
        video_track_selector,
        "probe_media_tracks",
        lambda *a, **kw: ([], []),
    )

    def fake_run_strategies(
        strategies, output_path, display_name, cancel_event=None, progress_callback=None
    ):
        output_path.write_bytes(b"partial failed output")
        return None

    monkeypatch.setattr(video_track_selector, "run_strategies", fake_run_strategies)

    ok = remux_selected_tracks(
        input_path=src_file,
        output_path=out_file,
        selected_stream_indices=[1],
        ffmpeg_bin=Path("ffmpeg"),
    )

    assert ok is False
    assert out_file.read_bytes() == b"intact existing output"
    assert _leftover_temp_files(tmp_path, out_file.stem) == []


def test_remux_selected_tracks_cleans_temp_file_on_cancellation(
    tmp_path, monkeypatch
):
    """Removes the temp file and never creates `output_path` when `InterruptedError` is raised."""
    src_file = tmp_path / "source.mkv"
    src_file.write_bytes(b"source mkv bytes")
    out_file = tmp_path / "cancelled.mp4"
    cancel_event = threading.Event()

    monkeypatch.setattr(
        video_track_selector,
        "probe_streams",
        lambda *a, **kw: StreamInfo(video_codec="h264", duration_seconds=60.0),
    )
    monkeypatch.setattr(
        video_track_selector,
        "probe_media_tracks",
        lambda *a, **kw: ([], []),
    )

    def fake_run_strategies(
        strategies, output_path, display_name, cancel_event=None, progress_callback=None
    ):
        output_path.write_bytes(b"partial cancelled output")
        raise InterruptedError("CANCELLED_BY_USER")

    monkeypatch.setattr(video_track_selector, "run_strategies", fake_run_strategies)

    with pytest.raises(InterruptedError):
        remux_selected_tracks(
            input_path=src_file,
            output_path=out_file,
            selected_stream_indices=[1],
            cancel_event=cancel_event,
            ffmpeg_bin=Path("ffmpeg"),
        )

    assert not out_file.exists()
    assert _leftover_temp_files(tmp_path, out_file.stem) == []


@pytest.mark.parametrize("target_ext", [".mp4", ".mov"])
@pytest.mark.parametrize("sub_codec", ["subrip", "ass", "ssa", "webvtt"])
def test_remux_selected_tracks_adds_mov_text_fallback_for_text_subtitles(
    tmp_path, monkeypatch, target_ext, sub_codec
):
    """Adds `-c copy -c:s mov_text` fallback strategies when text subtitles target MP4/MOV."""
    src_file = tmp_path / "source.mkv"
    src_file.write_bytes(b"source mkv bytes")
    out_file = tmp_path / f"movie{target_ext}"

    audio_tracks = [MediaTrack(stream_index=1, track_type="audio", codec="aac")]
    subtitle_tracks = [
        MediaTrack(stream_index=2, track_type="subtitle", codec=sub_codec)
    ]

    monkeypatch.setattr(
        video_track_selector,
        "probe_streams",
        lambda *a, **kw: StreamInfo(video_codec="h264", duration_seconds=90.0),
    )
    monkeypatch.setattr(
        video_track_selector,
        "probe_media_tracks",
        lambda *a, **kw: (audio_tracks, subtitle_tracks),
    )

    captured_strategies: list[tuple[str, list[str]]] = []

    def fake_run_strategies(
        strategies, output_path, display_name, cancel_event=None, progress_callback=None
    ):
        captured_strategies.extend(strategies)
        output_path.write_bytes(b"remuxed with mov_text")
        return "remux_mov_text_with_metadata"

    monkeypatch.setattr(video_track_selector, "run_strategies", fake_run_strategies)

    ok = remux_selected_tracks(
        input_path=src_file,
        output_path=out_file,
        selected_stream_indices=[1, 2],
        ffmpeg_bin=Path("ffmpeg"),
    )

    assert ok is True
    assert out_file.exists()

    strategy_map = dict(captured_strategies)
    assert "remux_mov_text_with_metadata" in strategy_map
    assert "remux_mov_text_minimal" in strategy_map

    mov_text_cmd = strategy_map["remux_mov_text_with_metadata"]
    assert "0:1" in mov_text_cmd
    assert "0:2" in mov_text_cmd
    assert mov_text_cmd[mov_text_cmd.index("-c") + 1] == "copy"
    assert mov_text_cmd[mov_text_cmd.index("-c:s") + 1] == "mov_text"


@pytest.mark.parametrize(
    "bitmap_codec", ["hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle"]
)
def test_remux_selected_tracks_drops_bitmap_subtitles_in_mp4_with_warning(
    tmp_path, monkeypatch, caplog, bitmap_codec
):
    """Drops incompatible bitmap subtitles with a warning while preserving compatible tracks."""
    src_file = tmp_path / "source.mkv"
    src_file.write_bytes(b"source mkv bytes")
    out_file = tmp_path / "movie.mp4"

    audio_tracks = [MediaTrack(stream_index=1, track_type="audio", codec="aac")]
    subtitle_tracks = [
        MediaTrack(stream_index=2, track_type="subtitle", codec=bitmap_codec),
        MediaTrack(stream_index=3, track_type="subtitle", codec="subrip"),
    ]

    monkeypatch.setattr(
        video_track_selector,
        "probe_streams",
        lambda *a, **kw: StreamInfo(video_codec="h264", duration_seconds=90.0),
    )
    monkeypatch.setattr(
        video_track_selector,
        "probe_media_tracks",
        lambda *a, **kw: (audio_tracks, subtitle_tracks),
    )

    captured_strategies: list[tuple[str, list[str]]] = []

    def fake_run_strategies(
        strategies, output_path, display_name, cancel_event=None, progress_callback=None
    ):
        captured_strategies.extend(strategies)
        output_path.write_bytes(b"remuxed without bitmap sub")
        return strategies[0][0]

    monkeypatch.setattr(video_track_selector, "run_strategies", fake_run_strategies)

    with caplog.at_level(logging.WARNING):
        ok = remux_selected_tracks(
            input_path=src_file,
            output_path=out_file,
            selected_stream_indices=[1, 2, 3],
            ffmpeg_bin=Path("ffmpeg"),
        )

    assert ok is True
    primary_cmd = captured_strategies[0][1]
    assert "0:1" in primary_cmd
    assert "0:2" not in primary_cmd
    assert "0:3" in primary_cmd
    assert any(
        "Dropping incompatible subtitle track #2" in rec.message
        and bitmap_codec in rec.message
        for rec in caplog.records
    )
    assert any(label == "remux_mov_text_with_metadata" for label, _ in captured_strategies)


@pytest.mark.parametrize(
    ("target_fmt", "codec", "expected"),
    [
        ("mp4", "subrip", "transcode"),
        ("mov", "ass", "transcode"),
        ("mp4", "mov_text", "copy"),
        ("mp4", "text", "copy"),
        ("mp4", "hdmv_pgs_subtitle", "incompatible"),
        ("mov", "dvd_subtitle", "incompatible"),
        ("mkv", "hdmv_pgs_subtitle", "copy"),
        ("mkv", "ass", "copy"),
        ("webm", "webvtt", "copy"),
        ("webm", "subrip", "transcode"),
        ("webm", "dvd_subtitle", "incompatible"),
        ("avi", "subrip", "incompatible"),
    ],
)
def test_classify_subtitle_codec_matrix(target_fmt, codec, expected):
    """Validates container-level subtitle disposition (`copy`, `transcode`, `incompatible`)."""
    assert classify_subtitle_codec(target_fmt, codec) == expected
