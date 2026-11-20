"""Unit tests for single-file and batch directory video downscaling engines."""

import threading
from pathlib import Path

import pytest

from src.video import video_directory_downscale, video_file_downscale
from src.video.utils.video_ffmpeg_utils import StreamInfo
from src.video.video_directory_downscale import directory_downscaler
from src.video.video_file_downscale import (
    build_downscale_filter,
    file_downscaler,
    resolve_target_height,
)

# --- Resolution & filter generation ---


@pytest.mark.parametrize(
    ("raw_input", "expected"),
    [
        ("1080p", 1080),
        ("720p", 720),
        ("480p", 480),
        (" 720P ", 720),
        (1080, 1080),
        (721, 720),  # Ensures even output
    ],
)
def test_resolve_target_height_validates_and_normalizes(raw_input, expected):
    """Normalizes preset labels and integer heights into even target pixel heights."""
    assert resolve_target_height(raw_input) == expected


@pytest.mark.parametrize("invalid_input", ["invalid", "0p", "1", 0, -480])
def test_resolve_target_height_rejects_invalid_values(invalid_input):
    """Raises ValueError for unsupported labels or dimensions smaller than 2px."""
    with pytest.raises(ValueError):
        resolve_target_height(invalid_input)


def test_build_downscale_filter_supports_landscape_portrait_and_even_dimensions():
    """Generates aspect-ratio-safe scale expressions handling both landscape and portrait videos."""
    vf_args = build_downscale_filter(target_height=720, is_10bit=False, keep_hevc=False)

    assert vf_args[0] == "-vf"
    scale_expr = vf_args[1]
    assert "720" in scale_expr
    assert "gte(iw\\,ih)" in scale_expr
    assert "-2" in scale_expr
    assert "trunc(iw/2)*2" in scale_expr
    assert "trunc(ih/2)*2" in scale_expr
    assert vf_args[2:] == ["-pix_fmt", "yuv420p"]


def test_build_downscale_filter_preserves_10bit_for_hevc():
    """Selects yuv420p10le pixel format when source is 10-bit and target encoder is HEVC."""
    vf_args = build_downscale_filter(target_height=1080, is_10bit=True, keep_hevc=True)
    assert vf_args[2:] == ["-pix_fmt", "yuv420p10le"]


@pytest.mark.parametrize(
    ("width", "height", "target", "expected"),
    [
        (3840, 2160, 1080, False),  # 4K landscape -> 1080p: must downscale
        (2160, 3840, 1080, False),  # 4K portrait -> 1080p: must downscale
        (1920, 1080, 1080, True),  # 1080p landscape -> 1080p: skip
        (1080, 1920, 1080, True),  # 1080p portrait -> 1080p: skip
        (1280, 720, 1080, True),  # 720p landscape -> 1080p: skip upscale
        (720, 1280, 1080, True),  # 720p portrait -> 1080p: skip upscale
        (854, 480, 720, True),  # 480p -> 720p: skip upscale
        (None, None, 720, False),  # Unknown dimensions: proceed safely
    ],
)
def should_skip_downscale(
    info: StreamInfo,
    target_height: int,
) -> bool:
    """Returns True if the video is already at or below `target_height`."""
    if info.width is None or info.height is None:
        return False
    if info.width <= 0 or info.height <= 0:
        return False
    return min(info.width, info.height) <= target_height


# --- Single-file downscaling engine ---


def test_file_downscaler_skips_upscale_and_copies_atomically(tmp_path, monkeypatch):
    """Copies source file untouched without invoking FFmpeg when resolution <= target."""
    src = tmp_path / "720p_clip.mp4"
    src.write_bytes(b"original-video-bytes")
    dst = tmp_path / "out" / "720p_clip.mp4"

    monkeypatch.setattr(video_file_downscale, "get_ffmpeg_path", lambda: Path("ffmpeg"))
    monkeypatch.setattr(
        video_file_downscale,
        "probe_streams",
        lambda *_: StreamInfo(
            video_codec="h264",
            audio_codecs=["aac"],
            width=1280,
            height=720,
            duration_seconds=10.0,
        ),
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("FFmpeg strategies must not run when video is already <= target.")

    monkeypatch.setattr(video_file_downscale, "run_strategies", fail_if_called)

    progress_events: list[tuple[float, float, float, float]] = []
    ok = file_downscaler(
        input_path=src,
        output_path=dst,
        resolution="1080p",
        file_progress_callback=lambda *vals: progress_events.append(vals),
    )

    assert ok is True
    assert dst.exists()
    assert dst.read_bytes() == b"original-video-bytes"
    assert src.read_bytes() == b"original-video-bytes"
    assert progress_events == [(10.0, 10.0, 0.0, 0.0)]


def test_file_downscaler_scales_4k_video_and_preserves_original(tmp_path, monkeypatch):
    """Runs FFmpeg downscale strategies on 4K inputs and leaves original file untouched."""
    src = tmp_path / "uhd_sample.mp4"
    src.write_bytes(b"raw-4k-payload")
    dst = tmp_path / "scaled" / "uhd_sample.mp4"

    monkeypatch.setattr(video_file_downscale, "get_ffmpeg_path", lambda: Path("ffmpeg"))
    monkeypatch.setattr(
        video_file_downscale,
        "probe_streams",
        lambda *_: StreamInfo(
            video_codec="h264",
            audio_codecs=["aac"],
            width=3840,
            height=2160,
            duration_seconds=30.0,
        ),
    )

    captured_strategies: list[tuple[str, list[str]]] = []

    def fake_run_strategies(strategies, tmp_output, display_name, cancel_event, progress_callback=None):
        captured_strategies.extend(strategies)
        tmp_output.write_bytes(b"downscaled-720p-payload")
        if progress_callback:
            progress_callback(15.0, 60.0, 2.0)
        return strategies[0][0]

    monkeypatch.setattr(video_file_downscale, "run_strategies", fake_run_strategies)

    progress_calls: list[tuple[float, float, float, float]] = []
    ok = file_downscaler(
        input_path=src,
        output_path=dst,
        resolution="720p",
        file_progress_callback=lambda *vals: progress_calls.append(vals),
    )

    assert ok is True
    assert dst.exists()
    assert dst.read_bytes() == b"downscaled-720p-payload"
    assert src.read_bytes() == b"raw-4k-payload"
    assert len(captured_strategies) >= 2
    assert any("720" in token for token in captured_strategies[0][1])
    assert progress_calls == [(30.0, 15.0, 60.0, 2.0)]


def test_file_downscaler_refuses_overwriting_source_file(tmp_path):
    """Refuses to process when input and output paths resolve to the same file."""
    src = tmp_path / "video.mp4"
    src.write_bytes(b"data")

    assert file_downscaler(input_path=src, output_path=src, resolution="720p") is False
    assert src.read_bytes() == b"data"


def test_file_downscaler_respects_cancellation(tmp_path):
    """Raises InterruptedError immediately if cancel_event is already set."""
    src = tmp_path / "video.mp4"
    src.write_bytes(b"data")
    dst = tmp_path / "out.mp4"

    cancel_event = threading.Event()
    cancel_event.set()

    with pytest.raises(InterruptedError):
        file_downscaler(
            input_path=src,
            output_path=dst,
            resolution="720p",
            cancel_event=cancel_event,
        )
    assert not dst.exists()


# --- Batch directory downscaling engine ---


def test_directory_downscaler_processes_batch_successfully(tmp_path, monkeypatch):
    """Scans directory and downscales all discovered video files into session output directory."""
    in_dir = tmp_path / "videos_in"
    out_dir = tmp_path / "videos_out"
    in_dir.mkdir()

    vid1 = in_dir / "clip_a.mp4"
    vid2 = in_dir / "clip_b.mkv"
    vid1.write_bytes(b"video-a")
    vid2.write_bytes(b"video-b")

    processed_pairs: list[tuple[str, str, int | str]] = []

    def fake_file_downscaler(
        input_path: Path,
        output_path: Path,
        resolution: str | int = "1080p",
        cancel_event=None,
        file_progress_callback=None,
    ) -> bool:
        processed_pairs.append((input_path.name, output_path.name, resolution))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"scaled")
        if file_progress_callback:
            file_progress_callback(10.0, 10.0, 30.0, 1.5)
        return True

    monkeypatch.setattr(
        video_directory_downscale, "file_downscaler", fake_file_downscaler
    )

    summary = directory_downscaler(
        input_dir=in_dir,
        output_dir=out_dir,
        resolution="720p",
    )

    assert summary["success"] == 2
    assert summary["failed"] == 0
    assert len(processed_pairs) == 2
    assert all(res == 720 for _, _, res in processed_pairs)
