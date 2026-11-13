"""Unit tests for pure parsing helpers and bounded buffering in `src.video.utils.ffmpeg_utils`.

Covers `parse_ffmpeg_stderr` / `probe_streams` against fixture strings (8-bit,
10-bit, 12-bit pixel formats, misleading stream metadata titles, `Duration: N/A`,
and attached cover art), `_parse_progress_line` for `-progress pipe:1`, and
bounded stderr memory buffering during `run_strategies`.
"""

import io
import subprocess
from pathlib import Path

import pytest

from src.video.utils import ffmpeg_utils
from src.video.utils.ffmpeg_utils import (
    STDERR_TAIL_BUFFER_SIZE,
    _parse_progress_line,
    _ProgressState,
    parse_ffmpeg_stderr,
    probe_streams,
    run_strategies,
)

# --- Stream probing & stderr parsing ---


def test_parse_ffmpeg_stderr_standard_8bit_video_and_audio():
    """Extracts video codec, audio codecs, pixel format, and duration from standard stderr."""
    stderr_fixture = """
Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'sample.mp4':
  Metadata:
    major_brand     : isom
  Duration: 00:01:30.50, start: 0.000000, bitrate: 1500 kb/s
  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(tv, bt709, progressive), 1920x1080 [SAR 1:1 DAR 16:9], 1350 kb/s, 30 fps
  Stream #0:1[0x2](eng): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 128 kb/s
"""
    info = parse_ffmpeg_stderr(stderr_fixture)

    assert info.video_codec == "h264", (
        f"Expected primary video codec 'h264', but got '{info.video_codec}'."
    )
    assert info.audio_codecs == ["aac"], (
        f"Expected audio codecs ['aac'], but got {info.audio_codecs}."
    )
    assert info.pix_fmt == "yuv420p", (
        f"Expected pixel format 'yuv420p', but got '{info.pix_fmt}'."
    )
    assert info.standard_pix_fmt is True, (
        "Standard 8-bit yuv420p stream was incorrectly flagged as non-standard pixel format."
    )
    assert info.is_10bit is False, (
        "Standard 8-bit yuv420p stream was falsely detected as 10-bit/high-bit-depth."
    )
    assert info.duration_seconds == 90.5, (
        f"Duration parsing regression: expected 90.5s, got {info.duration_seconds}s."
    )


@pytest.mark.parametrize(
    "pix_fmt_token",
    [
        "yuv420p10le",
        "yuv422p10le",
        "yuv444p10le",
        "p010le",
        "yuv420p12le",
        "yuv422p12le",
        "gbrp12le",
    ],
)
def test_parse_ffmpeg_stderr_detects_10bit_and_12bit_pixel_formats(pix_fmt_token):
    """Detects 10-bit and 12-bit formats strictly from the pixel format token."""
    stderr_fixture = f"""
Input #0, matroska,webm, from 'hdr_clip.mkv':
  Duration: 00:00:12.00, start: 0.000000, bitrate: 8000 kb/s
  Stream #0:0: Video: hevc (Main 10), {pix_fmt_token}(tv, bt2020nc/bt2020/smpte2084), 3840x2160, 23.98 fps
"""
    info = parse_ffmpeg_stderr(stderr_fixture)

    assert info.video_codec == "hevc", (
        f"Expected HEVC video codec, got '{info.video_codec}'."
    )
    assert info.pix_fmt == pix_fmt_token, (
        f"Pixel format extraction failed: expected '{pix_fmt_token}', got '{info.pix_fmt}'."
    )
    assert info.standard_pix_fmt is False, (
        f"High-bit-depth format '{pix_fmt_token}' was wrongly classified as standard 8-bit yuv420p."
    )
    assert info.is_10bit is True, (
        f"High-bit-depth detection failed for '{pix_fmt_token}': 10-bit/12-bit formats must set is_10bit=True."
    )


def test_parse_ffmpeg_stderr_avoids_false_positive_on_10bit_title_in_8bit_stream():
    """An 8-bit yuv420p stream whose metadata/handler mentions '10-bit' must not be flagged as 10-bit."""
    stderr_fixture = """
Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'fake_hdr_tag.mp4':
  Duration: 00:02:00.00, start: 0.000000, bitrate: 2000 kb/s
  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(progressive), 1280x720, 1900 kb/s, 60 fps, handler_name=10-bit Master Export
"""
    info = parse_ffmpeg_stderr(stderr_fixture)

    assert info.video_codec == "h264", (
        f"Expected 'h264' codec, got '{info.video_codec}'."
    )
    assert info.pix_fmt == "yuv420p", (
        f"Expected 'yuv420p', got '{info.pix_fmt}'."
    )
    assert info.standard_pix_fmt is True, (
        "8-bit yuv420p stream should have standard_pix_fmt=True regardless of handler metadata."
    )
    assert info.is_10bit is False, (
        "False positive regression: raw line substring matching flagged an 8-bit stream as 10-bit because of metadata text."
    )


def test_parse_ffmpeg_stderr_handles_duration_na_and_cover_art():
    """Returns duration_seconds=0.0 for `Duration: N/A` and ignores attached picture streams."""
    stderr_fixture = """
Input #0, mpegts, from 'live_capture.ts':
  Duration: N/A, start: 1.400000, bitrate: N/A
  Stream #0:0[0x100]: Video: mjpeg (Baseline), yuvj420p(pc, bt470bg/unknown/unknown), 600x600, 90k tbr (attached pic)
  Stream #0:1[0x101]: Video: hevc (Main 10), yuv420p10le(tv), 1920x1080, 59.94 fps
  Stream #0:2[0x102]: Audio: ac3, 48000 Hz, 5.1(side), fltp, 384 kb/s
  Stream #0:3[0x103]: Audio: aac (LC), 48000 Hz, stereo, fltp, 128 kb/s
"""
    info = parse_ffmpeg_stderr(stderr_fixture)

    assert info.duration_seconds == 0.0, (
        f"Streams with 'Duration: N/A' must report 0.0s duration, got {info.duration_seconds}s."
    )
    assert info.video_codec == "hevc", (
        f"Cover art stream ('attached pic') was not skipped; got video_codec='{info.video_codec}' instead of 'hevc'."
    )
    assert info.pix_fmt == "yuv420p10le", (
        f"Expected 'yuv420p10le' from main video stream, got '{info.pix_fmt}'."
    )
    assert info.is_10bit is True, (
        "Main 10-bit HEVC stream after cover art was not flagged as is_10bit=True."
    )
    assert info.audio_codecs == ["ac3", "aac"], (
        f"Expected all audio streams ['ac3', 'aac'] to be collected, got {info.audio_codecs}."
    )


def test_probe_streams_delegates_to_stderr_parser(monkeypatch):
    """Verifies `probe_streams` parses mocked subprocess stderr without invoking real FFmpeg."""
    sample_stderr = (
        b"  Duration: 00:00:05.25, start: 0.000000, bitrate: 500 kb/s\n"
        b"  Stream #0:0: Video: vp9, yuv420p, 640x360, 30 fps\n"
    )

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0], returncode=1, stdout=b"", stderr=sample_stderr
        )

    monkeypatch.setattr(ffmpeg_utils.subprocess, "run", fake_run)

    info = probe_streams(Path("ffmpeg"), Path("video.webm"))
    assert info.video_codec == "vp9", (
        f"probe_streams failed to delegate video codec parsing: expected 'vp9', got '{info.video_codec}'."
    )
    assert info.pix_fmt == "yuv420p", (
        f"probe_streams failed to delegate pixel format parsing: expected 'yuv420p', got '{info.pix_fmt}'."
    )
    assert info.duration_seconds == 5.25, (
        f"probe_streams failed to delegate duration parsing: expected 5.25s, got {info.duration_seconds}s."
    )
    assert info.is_10bit is False, (
        "probe_streams falsely marked an 8-bit VP9 stream as 10-bit."
    )


# --- Progress parser ---


def test_parse_progress_line_updates_metrics_and_triggers_on_progress_key():
    """Parses `out_time_us`, `fps`, `speed`, and returns True only on `progress=`."""
    state = _ProgressState()

    assert _parse_progress_line("frame=120\n", state) is False, (
        "Progress parser triggered callback early on 'frame=' key instead of waiting for 'progress='."
    )
    assert _parse_progress_line("fps=48.50\n", state) is False, (
        "Progress parser triggered callback early on 'fps=' key."
    )
    assert _parse_progress_line("out_time_us=2500000\n", state) is False, (
        "Progress parser triggered callback early on 'out_time_us=' key."
    )
    assert _parse_progress_line("speed=1.62x\n", state) is False, (
        "Progress parser triggered callback early on 'speed=' key."
    )
    assert _parse_progress_line("progress=continue\n", state) is True, (
        "Progress parser failed to emit tick when 'progress=continue' boundary was reached."
    )

    assert state.out_time == pytest.approx(2.5), (
        f"Microsecond timestamp conversion failed: expected 2.5s, got {state.out_time}s."
    )
    assert state.fps == pytest.approx(48.5), (
        f"FPS parsing failed: expected 48.5, got {state.fps}."
    )
    assert state.speed == pytest.approx(1.62), (
        f"Speed multiplier parsing failed: expected 1.62, got {state.speed}."
    )


def test_parse_progress_line_falls_back_to_out_time_when_us_is_zero():
    """Uses `out_time=HH:MM:SS.ms` when `out_time_us` has not been set yet."""
    state = _ProgressState()

    assert _parse_progress_line("out_time=01:02:03.500000\n", state) is False, (
        "Progress parser triggered callback early on 'out_time=' key."
    )
    assert state.out_time == pytest.approx(3723.5), (
        f"Fallback HH:MM:SS.ms timestamp parsing failed: expected 3723.5s, got {state.out_time}s."
    )

    assert _parse_progress_line("progress=end\n", state) is True, (
        "Progress parser failed to emit final tick on 'progress=end'."
    )


def test_parse_progress_line_ignores_malformed_or_na_values():
    """Handles `N/A` values and malformed lines without raising exceptions."""
    state = _ProgressState()

    assert _parse_progress_line("", state) is False, (
        "Empty progress line must be ignored."
    )
    assert _parse_progress_line("not_a_key_value_line", state) is False, (
        "Malformed progress line without '=' delimiter must be ignored."
    )
    assert _parse_progress_line("out_time_us=N/A", state) is False, (
        "'out_time_us=N/A' should be ignored safely."
    )
    assert _parse_progress_line("out_time=N/A", state) is False, (
        "'out_time=N/A' should be ignored safely."
    )
    assert _parse_progress_line("fps=N/A", state) is False, (
        "'fps=N/A' should be ignored safely."
    )
    assert _parse_progress_line("speed=N/A", state) is False, (
        "'speed=N/A' should be ignored safely."
    )
    assert _parse_progress_line("progress=continue", state) is True, (
        "Valid 'progress=continue' must still trigger callback after N/A metrics."
    )

    assert state.out_time == 0.0, (
        f"Invalid 'out_time' mutated state away from 0.0: got {state.out_time}."
    )
    assert state.fps == 0.0, (
        f"Invalid 'fps' mutated state away from 0.0: got {state.fps}."
    )
    assert state.speed == 0.0, (
        f"Invalid 'speed' mutated state away from 0.0: got {state.speed}."
    )


# --- Bounded stderr buffering ---


def test_run_strategies_caps_stderr_buffer_and_logs_only_tail(
    tmp_path, monkeypatch, caplog
):
    """Ensures stderr accumulation stays bounded (`STDERR_TAIL_BUFFER_SIZE`) on verbose failures."""
    total_lines = STDERR_TAIL_BUFFER_SIZE * 10
    verbose_stderr = "".join(
        f"frame={i} diagnostic error detail line {i}\n"
        for i in range(total_lines)
    ).encode("utf-8")

    class FakeFailingProcess:
        def __init__(self):
            self.stdout = io.BytesIO(b"")
            self.stderr = io.BytesIO(verbose_stderr)
            self.returncode = 1

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            return self.returncode

        def terminate(self):
            pass

        def kill(self):
            pass

    monkeypatch.setattr(
        ffmpeg_utils.subprocess, "Popen", lambda *a, **kw: FakeFailingProcess()
    )

    output_file = tmp_path / "failed_out.mp4"
    with caplog.at_level("WARNING", logger=ffmpeg_utils.__name__):
        result = run_strategies(
            [("mock strategy", ["ffmpeg", "-i", "in.mp4", str(output_file)])],
            output_file,
            "in.mp4",
        )

    assert result is None, (
        "Expected run_strategies to return None when the mocked strategy exits with returncode=1."
    )
    warning_messages = "\n".join(rec.getMessage() for rec in caplog.records)
    assert f"diagnostic error detail line {total_lines - 1}" in warning_messages, (
        "Stderr tail logging failed: the final stderr error line was missing from the warning log."
    )
    assert "diagnostic error detail line 0\n" not in warning_messages, (
        "Unbounded stderr buffer regression: early stderr lines leaked into the warning output instead of keeping only the bounded tail."
    )