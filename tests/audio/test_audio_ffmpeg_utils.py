"""Unit tests for FFmpeg audio stream parsing, bitrate mapping, and strategy execution."""

import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.audio.utils import audio_ffmpeg_utils


def test_parse_audio_stderr_extracts_duration_codec_samplerate_and_layout():
    """`parse_audio_stderr` must extract duration, primary audio codec, sample rate, and layout."""
    sample_stderr = (
        "Input #0, mp3, from 'song.mp3':\n"
        "  Duration: 00:02:15.50, start: 0.025057, bitrate: 320 kb/s\n"
        "  Stream #0:0: Audio: mp3 (mp3float), 44100 Hz, stereo, fltp, 320 kb/s\n"
        "  Stream #0:1: Video: mjpeg (Baseline), yuvj420p(pc), 500x500 [SAR 1:1 DAR 1:1], 90k tbr (attached pic)\n"
    )
    info = audio_ffmpeg_utils.parse_audio_stderr(sample_stderr)

    assert info.duration_seconds == 135.5, (
        f"[audio] Expected parsed duration 135.5s, got {info.duration_seconds}s."
    )
    assert info.audio_codecs == ["mp3"], (
        f"[audio] Expected audio_codecs=['mp3'], got {info.audio_codecs}."
    )
    assert info.primary_codec == "mp3", (
        f"[audio] Expected primary_codec='mp3', got {info.primary_codec!r}."
    )
    assert info.sample_rate == 44100, (
        f"[audio] Expected sample_rate=44100, got {info.sample_rate}."
    )
    assert info.channel_layout == "stereo" and info.channels == 2, (
        f"[audio] Expected stereo (channels=2), got layout={info.channel_layout!r}, channels={info.channels}."
    )

    mono_stderr = (
        "  Duration: 00:00:10.00, start: 0.000000, bitrate: 128 kb/s\n"
        "  Stream #0:0: Audio: vorbis, 44100 Hz, mono, fltp, 128 kb/s\n"
    )
    mono_info = audio_ffmpeg_utils.parse_audio_stderr(mono_stderr)
    assert mono_info.channel_layout == "mono" and mono_info.channels == 1, (
        f"[audio] Expected mono (channels=1), got layout={mono_info.channel_layout!r}, channels={mono_info.channels}."
    )


def test_parse_audio_stderr_accepts_streams_without_explicit_sample_rate():
    """`parse_audio_stderr` must parse exotic streams (e.g., WMA/AIFF) that omit `<N> Hz`."""
    exotic_stderr = (
        "Input #0, asf, from 'legacy.wma':\n"
        "  Duration: 00:01:05.00, start: 0.000000, bitrate: 128 kb/s\n"
        "  Stream #0:0(eng): Audio: wmav2 (a[1][0][0] / 0x0161), stereo, fltp, 128 kb/s\n"
    )
    info = audio_ffmpeg_utils.parse_audio_stderr(exotic_stderr)

    assert info.audio_codecs == ["wmav2"], (
        f"[audio] Expected audio_codecs=['wmav2'] when sample rate is omitted, got {info.audio_codecs}."
    )
    assert info.primary_codec == "wmav2", (
        f"[audio] Expected primary_codec='wmav2', got {info.primary_codec!r}."
    )
    assert info.sample_rate == 0, (
        f"[audio] Expected default sample_rate=0 when omitted from stream line, got {info.sample_rate}."
    )
    assert info.channel_layout == "stereo" and info.channels == 2, (
        f"[audio] Expected stereo (channels=2), got layout={info.channel_layout!r}, channels={info.channels}."
    )

    mono_exotic_stderr = (
        "  Duration: 00:00:12.00, bitrate: 64 kb/s\n"
        "  Stream #0:0: Audio: pcm_s16be, mono, s16, 64 kb/s\n"
    )
    mono_info = audio_ffmpeg_utils.parse_audio_stderr(mono_exotic_stderr)
    assert mono_info.primary_codec == "pcm_s16be" and mono_info.channels == 1, (
        f"[audio] Expected mono pcm_s16be stream without sample rate to parse cleanly, got {mono_info}."
    )


def test_parse_audio_stderr_returns_empty_info_when_no_audio_stream():
    """`parse_audio_stderr` must return empty `audio_codecs` for non-audio or invalid inputs."""
    info = audio_ffmpeg_utils.parse_audio_stderr("Invalid data found when processing input")
    assert info.audio_codecs == [] and info.primary_codec is None, (
        f"[audio] Expected empty AudioStreamInfo for invalid input, got {info}."
    )


def test_quality_to_bitrate_kbps_bounds_and_vorbis_mono_ceiling():
    """`quality_to_bitrate_kbps` must map 1..100 linearly, enforce codec floors, clamp out-of-range inputs, and cap mono OGG at 256k."""
    assert audio_ffmpeg_utils.quality_to_bitrate_kbps("mp3", 1) == 48, (
        "[audio] Quality 1 for MP3 must map to minimum bitrate 48 kbps."
    )
    assert audio_ffmpeg_utils.quality_to_bitrate_kbps("mp3", 100) == 320, (
        "[audio] Quality 100 for MP3 must map to maximum bitrate 320 kbps."
    )
    assert audio_ffmpeg_utils.quality_to_bitrate_kbps("m4a", 1) == 64, (
        "[audio] Quality 1 for M4A must map to minimum bitrate 64 kbps to preserve stereo AAC quality."
    )
    assert audio_ffmpeg_utils.quality_to_bitrate_kbps("m4a", 100) == 320, (
        "[audio] Quality 100 for M4A must map to maximum bitrate 320 kbps."
    )
    assert audio_ffmpeg_utils.quality_to_bitrate_kbps("aac", 1) == 64, (
        "[audio] Quality 1 for AAC must map to minimum bitrate 64 kbps to preserve stereo AAC quality."
    )
    assert audio_ffmpeg_utils.quality_to_bitrate_kbps("aac", 100) == 320, (
        "[audio] Quality 100 for AAC must map to maximum bitrate 320 kbps."
    )
    assert audio_ffmpeg_utils.quality_to_bitrate_kbps("ogg", 100, channels=2) == 320, (
        "[audio] Stereo OGG at quality 100 must retain full 320 kbps ceiling."
    )
    assert audio_ffmpeg_utils.quality_to_bitrate_kbps("ogg", 100, channels=1) == 256, (
        "[audio] Mono OGG at quality 100 must cap at 256 kbps to satisfy libvorbis single-channel limits."
    )
    assert audio_ffmpeg_utils.quality_to_bitrate_kbps("opus", 1) == 32, (
        "[audio] Quality 1 for Opus must map to minimum bitrate 32 kbps."
    )
    assert audio_ffmpeg_utils.quality_to_bitrate_kbps("opus", 100) == 192, (
        "[audio] Quality 100 for Opus must map to maximum bitrate 192 kbps."
    )
    assert audio_ffmpeg_utils.quality_to_bitrate_kbps("mp3", -20) == 48, (
        "[audio] Negative quality values must be clamped to 1 (48 kbps)."
    )
    assert audio_ffmpeg_utils.quality_to_bitrate_kbps("mp3", 999) == 320, (
        "[audio] Quality values > 100 must be clamped to 100 (320 kbps)."
    )


@pytest.mark.parametrize(
    ("fmt", "quality", "channels", "expected_tokens"),
    [
        ("mp3", None, 2, ["-c:a", "libmp3lame", "-b:a", "192k"]),
        ("mp3", 50, 2, ["-c:a", "libmp3lame", "-b:a", "183k"]),
        ("m4a", None, 2, ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]),
        ("m4a", 50, 2, ["-c:a", "aac", "-b:a", "191k", "-movflags", "+faststart"]),
        ("aac", None, 2, ["-c:a", "aac", "-b:a", "192k", "-f", "adts"]),
        ("aac", 50, 2, ["-c:a", "aac", "-b:a", "191k", "-f", "adts"]),
        ("opus", None, 2, ["-c:a", "libopus", "-b:a", "128k", "-ar", "48000"]),
        ("ogg", None, 2, ["-c:a", "libvorbis", "-b:a", "192k"]),
        ("ogg", 100, 2, ["-c:a", "libvorbis", "-b:a", "320k"]),
        ("ogg", 100, 1, ["-c:a", "libvorbis", "-b:a", "256k"]),
        ("flac", None, 2, ["-c:a", "flac", "-compression_level", "5"]),
        ("wav", None, 2, ["-c:a", "pcm_s16le"]),
    ],
)
def test_get_audio_codec_args_supported_formats(
    fmt, quality, channels, expected_tokens
):
    """`get_audio_codec_args` must return valid encoder flags for every target format and channel count."""
    args = audio_ffmpeg_utils.get_audio_codec_args(
        fmt, quality=quality, channels=channels
    )
    assert args == expected_tokens, (
        f"[audio] Codec args mismatch for format='{fmt}', quality={quality}, channels={channels}: "
        f"got {args}, expected {expected_tokens}."
    )


def test_get_audio_codec_args_rejects_unknown_format():
    """`get_audio_codec_args` must raise ValueError for unsupported target formats."""
    with pytest.raises(ValueError, match="Unsupported target audio format"):
        audio_ffmpeg_utils.get_audio_codec_args("wma")


def test_parse_progress_line_tracks_time_and_speed():
    """`_parse_progress_line` must accumulate `out_time` and `speed` and emit on `progress=`."""
    state = audio_ffmpeg_utils._ProgressState()

    assert audio_ffmpeg_utils._parse_progress_line("out_time_us=1500000", state) is False, (
        "[audio] Progress parser should not emit a tick before the 'progress=' boundary."
    )
    assert state.out_time == pytest.approx(1.5), (
        f"[audio] Expected out_time=1.5s from out_time_us=1500000, got {state.out_time}."
    )

    assert audio_ffmpeg_utils._parse_progress_line("speed=12.5x", state) is False, (
        "[audio] Progress parser should not emit a tick on 'speed=' alone."
    )
    assert state.speed == pytest.approx(12.5), (
        f"[audio] Expected speed=12.5 from '12.5x', got {state.speed}."
    )

    assert audio_ffmpeg_utils._parse_progress_line("progress=continue", state) is True, (
        "[audio] Progress parser must emit a tick when 'progress=continue' is reached."
    )


def test_run_audio_strategies_falls_back_and_cleans_partial_output(
    tmp_path: Path, monkeypatch
):
    """If strategy 1 fails and leaves a partial file, strategy 2 must run and succeed."""
    output_path = tmp_path / "out.mp3"
    attempts: list[str] = []

    class _FakeProc:
        def __init__(self, should_succeed: bool):
            self.should_succeed = should_succeed
            self.returncode = 0 if should_succeed else 1
            self.stdout = MagicMock()
            self.stdout.readline = MagicMock(
                side_effect=[b"out_time_us=1000000\n", b"progress=end\n", b""]
            )
            self.stderr = MagicMock()
            self.stderr.readline = MagicMock(side_effect=[b"encoder error\n", b""])

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            if self.should_succeed:
                output_path.write_bytes(b"valid-audio-bytes")
            else:
                output_path.write_bytes(b"corrupt-partial")
            return self.returncode

    def _fake_popen(cmd, **kwargs):
        label = cmd[0]
        attempts.append(label)
        return _FakeProc(should_succeed=(label == "rescue_cmd"))

    monkeypatch.setattr(audio_ffmpeg_utils.subprocess, "Popen", _fake_popen)

    progress_ticks: list[tuple[float, float, float]] = []
    used = audio_ffmpeg_utils.run_audio_strategies(
        strategies=[
            ("primary", ["primary_cmd"]),
            ("rescue", ["rescue_cmd"]),
        ],
        output_path=output_path,
        display_name="broken.wav",
        progress_callback=lambda t, fps, spd: progress_ticks.append((t, fps, spd)),
    )

    assert used == "rescue", (
        f"[audio] Expected fallback strategy 'rescue' to succeed after primary failed, got {used!r}."
    )
    assert attempts == ["primary_cmd", "rescue_cmd"], (
        f"[audio] Expected both strategies to be attempted in order, got {attempts}."
    )
    assert output_path.read_bytes() == b"valid-audio-bytes", (
        "[audio] Partial output from failed first strategy was not replaced by successful rescue output."
    )
    assert progress_ticks and progress_ticks[-1][1] == 0.0, (
        f"[audio] Expected audio progress callback to report fps=0.0, got {progress_ticks}."
    )


def test_run_audio_strategies_raises_interrupted_error_when_cancelled(tmp_path: Path):
    """`run_audio_strategies` must abort immediately with `InterruptedError` if `cancel_event` is set."""
    cancel = threading.Event()
    cancel.set()
    out = tmp_path / "cancelled.mp3"

    with pytest.raises(InterruptedError, match="CANCELLED_BY_USER"):
        audio_ffmpeg_utils.run_audio_strategies(
            strategies=[("primary", ["ffmpeg"])],
            output_path=out,
            display_name="track.wav",
            cancel_event=cancel,
        )


def test_terminate_active_processes_kills_orphans_and_removes_partials(
    tmp_path: Path, monkeypatch
):
    """`terminate_active_processes` must terminate running FFmpeg processes and delete tracked partial files."""
    partial_file = tmp_path / "orphan_partial.mp3"
    started = threading.Event()
    release = threading.Event()

    class _HangingProc:
        def __init__(self, *args, **kwargs):
            self.returncode = None
            self.terminated = False
            self.killed = False
            self.stdout = MagicMock()
            self.stdout.readline = MagicMock(side_effect=self._read_stdout)
            self.stderr = MagicMock()
            self.stderr.readline = MagicMock(return_value=b"")
            partial_file.write_bytes(b"partial-audio-stream")
            started.set()

        def _read_stdout(self):
            release.wait(timeout=5.0)
            return b""

        def poll(self):
            return self.returncode

        def terminate(self):
            self.terminated = True
            self.returncode = -15
            release.set()

        def kill(self):
            self.killed = True
            self.returncode = -9
            release.set()

        def wait(self, timeout=None):
            release.wait(timeout=5.0)
            return self.returncode if self.returncode is not None else -15

    created_procs: list[_HangingProc] = []

    def _fake_popen(*args, **kwargs):
        proc = _HangingProc(*args, **kwargs)
        created_procs.append(proc)
        return proc

    monkeypatch.setattr(audio_ffmpeg_utils.subprocess, "Popen", _fake_popen)

    worker = threading.Thread(
        target=audio_ffmpeg_utils.run_audio_strategies,
        kwargs={
            "strategies": [("primary", ["ffmpeg", "-i", "in.wav", str(partial_file)])],
            "output_path": partial_file,
            "display_name": "in.wav",
        },
        daemon=True,
    )
    worker.start()
    assert started.wait(timeout=3.0), (
        "[audio] Simulated FFmpeg process did not start within the timeout window."
    )

    audio_ffmpeg_utils.terminate_active_processes()
    worker.join(timeout=3.0)

    assert created_procs and (created_procs[0].terminated or created_procs[0].killed), (
        "[audio] Expected `terminate_active_processes` to call terminate() or kill() on active FFmpeg process."
    )
    assert not partial_file.exists(), (
        f"[audio] Expected `terminate_active_processes` to delete tracked partial file '{partial_file}'."
    )