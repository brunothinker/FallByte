"""Comprehensive unit and integration tests for the isolated audio engine (`src/audio/`).

Follows the project's descriptive assertion standard so every failure reports
both the broken invariant and the observed state.
"""

import ast
import subprocess
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.audio import (
    audio_directory_compression,
    audio_directory_conversion,
    audio_file_compression,
    audio_file_conversion,
)
from src.audio.utils import audio_scanner, binary_manager, ffmpeg_audio_utils
from src.formats import (
    AUDIO_TARGET_FORMATS,
    SUPPORTED_AUDIO_EXTENSIONS,
    UNCOMPRESSIBLE_AUDIO_FORMATS,
)

# ---------------------------------------------------------------------------
# Fixtures (self-contained so the suite runs without editing conftest.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_audio_factory(tmp_path: Path):
    """Generates real audio files using the bundled FFmpeg `lavfi` sine source."""
    ffmpeg_bin = binary_manager.get_ffmpeg_path()

    def _create(
        filename: str = "sample.wav",
        duration: float = 1.5,
        frequency: int = 440,
        bitrate: str | None = None,
        channels: int = 2,
        with_cover_art: bool = False,
    ) -> Path:
        out_path = tmp_path / filename
        out_path.parent.mkdir(parents=True, exist_ok=True)
        ext = out_path.suffix.lower().lstrip(".")

        cmd = [
            str(ffmpeg_bin),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:sample_rate=44100:duration={duration}",
        ]

        if with_cover_art:
            cmd.extend(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c=blue:s=32x32:d={duration}",
                    "-map",
                    "0:a:0",
                    "-map",
                    "1:v:0",
                    "-disposition:v:0",
                    "attached_pic",
                ]
            )

        cmd.extend(["-ac", str(channels)])

        if ext == "mp3":
            cmd.extend(["-c:a", "libmp3lame", "-b:a", bitrate or "192k"])
        elif ext == "m4a":
            cmd.extend(["-c:a", "aac", "-b:a", bitrate or "192k"])
        elif ext == "opus":
            cmd.extend(["-c:a", "libopus", "-b:a", bitrate or "128k", "-ar", "48000"])
        elif ext == "ogg":
            cmd.extend(["-c:a", "libvorbis", "-b:a", bitrate or "192k"])
        elif ext == "flac":
            cmd.extend(["-c:a", "flac"])
        elif ext == "wav":
            cmd.extend(["-c:a", "pcm_s16le"])
        elif ext == "aiff":
            cmd.extend(["-c:a", "pcm_s16be"])
        elif ext == "aac":
            cmd.extend(["-c:a", "aac", "-b:a", bitrate or "192k", "-f", "adts"])

        cmd.append(str(out_path))
        subprocess.run(cmd, check=True)
        assert out_path.exists() and out_path.stat().st_size > 0, (
            f"Fixture failed to generate sample audio at '{out_path}'."
        )
        return out_path

    return _create


# ---------------------------------------------------------------------------
# 1. Architectural Isolation & Format Constants
# ---------------------------------------------------------------------------


def test_audio_module_has_zero_cross_imports_from_video_or_image():
    """Enforces domain isolation: `src/audio/` must never import `src.video` or `src.image`."""
    audio_root = Path(__file__).resolve().parents[2] / "src" / "audio"
    py_files = list(audio_root.rglob("*.py"))
    assert py_files, f"Expected Python files under '{audio_root}', found none."

    forbidden_prefixes = ("src.video", "src.image")
    violations: list[str] = []

    for py_file in py_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(forbidden_prefixes):
                        violations.append(f"{py_file.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith(forbidden_prefixes):
                    violations.append(f"{py_file.name}: from {node.module} import ...")

    assert not violations, (
        "Architectural isolation broken: `src/audio/` imported forbidden domain modules: "
        f"{violations}"
    )


def test_audio_format_constants_consistency():
    """Verifies that target and uncompressible audio formats align with supported extensions."""
    expected_exts = {
        ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".wav", ".wma", ".aiff"
    }
    assert SUPPORTED_AUDIO_EXTENSIONS == expected_exts, (
        f"SUPPORTED_AUDIO_EXTENSIONS mismatch: got {SUPPORTED_AUDIO_EXTENSIONS}, "
        f"expected {expected_exts}."
    )

    for fmt in AUDIO_TARGET_FORMATS:
        assert f".{fmt}" in SUPPORTED_AUDIO_EXTENSIONS, (
            f"Target conversion format '{fmt}' is missing from SUPPORTED_AUDIO_EXTENSIONS."
        )

    for fmt_upper in UNCOMPRESSIBLE_AUDIO_FORMATS:
        assert f".{fmt_upper.lower()}" in SUPPORTED_AUDIO_EXTENSIONS, (
            f"Uncompressible audio format '{fmt_upper}' is not registered in "
            "SUPPORTED_AUDIO_EXTENSIONS."
        )


# ---------------------------------------------------------------------------
# 2. Scanner (`src/audio/utils/audio_scanner.py`)
# ---------------------------------------------------------------------------


def test_scan_audio_files_recursive_and_non_recursive(tmp_path: Path):
    """Scanner must find supported audio files case-insensitively and honor `recursive`."""
    (tmp_path / "track_b.MP3").write_bytes(b"fake")
    (tmp_path / "track_a.flac").write_bytes(b"fake")
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")
    (tmp_path / "video.mp4").write_bytes(b"ignore")

    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "nested_c.OpUs").write_bytes(b"fake")

    top_only = audio_scanner.scan_audio_files(tmp_path, recursive=False)
    assert [p.name for p in top_only] == ["track_a.flac", "track_b.MP3"], (
        f"Non-recursive scan should return only sorted top-level audio files, "
        f"got {[p.name for p in top_only]}."
    )

    all_files = audio_scanner.scan_audio_files(tmp_path, recursive=True)
    assert [p.name for p in all_files] == [
        "nested_c.OpUs",
        "track_a.flac",
        "track_b.MP3",
    ], (
        f"Recursive scan should return all 3 sorted audio files across subfolders, "
        f"got {[p.name for p in all_files]}."
    )


def test_scan_audio_files_handles_invalid_directory(tmp_path: Path):
    """Scanner must return an empty list without raising for missing paths or regular files."""
    missing = tmp_path / "does_not_exist"
    assert audio_scanner.scan_audio_files(missing) == [], (
        "Scanning a non-existent directory must safely return an empty list."
    )

    regular_file = tmp_path / "file.mp3"
    regular_file.write_bytes(b"data")
    assert audio_scanner.scan_audio_files(regular_file) == [], (
        "Scanning a file path instead of a directory must safely return an empty list."
    )


# ---------------------------------------------------------------------------
# 3. Binary Manager (`src/audio/utils/binary_manager.py`)
# ---------------------------------------------------------------------------


def test_binary_manager_resolves_linux_and_windows(tmp_path: Path, monkeypatch):
    """`get_ffmpeg_path` must resolve OS-specific paths, chmod +x on Linux, and validate existence."""
    fake_root = tmp_path / "repo"
    linux_bin = fake_root / "resources" / "bin" / "linux" / "ffmpeg"
    win_bin = fake_root / "resources" / "bin" / "windows" / "ffmpeg.exe"
    linux_bin.parent.mkdir(parents=True)
    win_bin.parent.mkdir(parents=True)
    linux_bin.write_bytes(b"#!/bin/sh\n")
    linux_bin.chmod(0o644)
    win_bin.write_bytes(b"MZ")

    fake_module_file = fake_root / "src" / "audio" / "utils" / "binary_manager.py"
    fake_module_file.parent.mkdir(parents=True)
    monkeypatch.setattr(binary_manager, "__file__", str(fake_module_file))

    monkeypatch.setattr(binary_manager.platform, "system", lambda: "Linux")
    resolved_linux = binary_manager.get_ffmpeg_path()
    assert resolved_linux == linux_bin, (
        f"Expected Linux FFmpeg path '{linux_bin}', got '{resolved_linux}'."
    )
    assert resolved_linux.stat().st_mode & 0o111, (
        "Expected `get_ffmpeg_path` to grant execute permission (+x) on Linux."
    )

    monkeypatch.setattr(binary_manager.platform, "system", lambda: "Windows")
    resolved_win = binary_manager.get_ffmpeg_path()
    assert resolved_win == win_bin, (
        f"Expected Windows FFmpeg path '{win_bin}', got '{resolved_win}'."
    )

    monkeypatch.setattr(binary_manager.platform, "system", lambda: "Darwin")
    with pytest.raises(OSError, match="Unsupported operating system"):
        binary_manager.get_ffmpeg_path()

    linux_bin.unlink()
    monkeypatch.setattr(binary_manager.platform, "system", lambda: "Linux")
    with pytest.raises(FileNotFoundError, match="FFmpeg binary not found"):
        binary_manager.get_ffmpeg_path()


# ---------------------------------------------------------------------------
# 4. FFmpeg Audio Utils (`src/audio/utils/ffmpeg_audio_utils.py`)
# ---------------------------------------------------------------------------


def test_parse_audio_stderr_extracts_duration_codec_samplerate_and_layout():
    """`parse_audio_stderr` must extract duration, primary audio codec, sample rate, and layout."""
    sample_stderr = (
        "Input #0, mp3, from 'song.mp3':\n"
        "  Duration: 00:02:15.50, start: 0.025057, bitrate: 320 kb/s\n"
        "  Stream #0:0: Audio: mp3 (mp3float), 44100 Hz, stereo, fltp, 320 kb/s\n"
        "  Stream #0:1: Video: mjpeg (Baseline), yuvj420p(pc), 500x500 [SAR 1:1 DAR 1:1], 90k tbr (attached pic)\n"
    )
    info = ffmpeg_audio_utils.parse_audio_stderr(sample_stderr)

    assert info.duration_seconds == 135.5, (
        f"Expected parsed duration 135.5s, got {info.duration_seconds}s."
    )
    assert info.audio_codecs == ["mp3"], (
        f"Expected audio_codecs=['mp3'], got {info.audio_codecs}."
    )
    assert info.primary_codec == "mp3", (
        f"Expected primary_codec='mp3', got {info.primary_codec!r}."
    )
    assert info.sample_rate == 44100, (
        f"Expected sample_rate=44100, got {info.sample_rate}."
    )
    assert info.channel_layout == "stereo" and info.channels == 2, (
        f"Expected stereo (channels=2), got layout={info.channel_layout!r}, channels={info.channels}."
    )

    mono_stderr = (
        "  Duration: 00:00:10.00, start: 0.000000, bitrate: 128 kb/s\n"
        "  Stream #0:0: Audio: vorbis, 44100 Hz, mono, fltp, 128 kb/s\n"
    )
    mono_info = ffmpeg_audio_utils.parse_audio_stderr(mono_stderr)
    assert mono_info.channel_layout == "mono" and mono_info.channels == 1, (
        f"Expected mono (channels=1), got layout={mono_info.channel_layout!r}, channels={mono_info.channels}."
    )


def test_parse_audio_stderr_returns_empty_info_when_no_audio_stream():
    """`parse_audio_stderr` must return empty `audio_codecs` for non-audio or invalid inputs."""
    info = ffmpeg_audio_utils.parse_audio_stderr("Invalid data found when processing input")
    assert info.audio_codecs == [] and info.primary_codec is None, (
        f"Expected empty AudioStreamInfo for invalid input, got {info}."
    )


def test_quality_to_bitrate_kbps_bounds_and_vorbis_mono_ceiling():
    """`quality_to_bitrate_kbps` must map 1..100 linearly, clamp out-of-range inputs, and cap mono OGG at 256k."""
    assert ffmpeg_audio_utils.quality_to_bitrate_kbps("mp3", 1) == 48, (
        "Quality 1 for MP3 must map to minimum bitrate 48 kbps."
    )
    assert ffmpeg_audio_utils.quality_to_bitrate_kbps("mp3", 100) == 320, (
        "Quality 100 for MP3 must map to maximum bitrate 320 kbps."
    )
    assert ffmpeg_audio_utils.quality_to_bitrate_kbps("ogg", 100, channels=2) == 320, (
        "Stereo OGG at quality 100 must retain full 320 kbps ceiling."
    )
    assert ffmpeg_audio_utils.quality_to_bitrate_kbps("ogg", 100, channels=1) == 256, (
        "Mono OGG at quality 100 must cap at 256 kbps to satisfy libvorbis single-channel limits."
    )
    assert ffmpeg_audio_utils.quality_to_bitrate_kbps("opus", 1) == 32, (
        "Quality 1 for Opus must map to minimum bitrate 32 kbps."
    )
    assert ffmpeg_audio_utils.quality_to_bitrate_kbps("opus", 100) == 192, (
        "Quality 100 for Opus must map to maximum bitrate 192 kbps."
    )
    assert ffmpeg_audio_utils.quality_to_bitrate_kbps("mp3", -20) == 48, (
        "Negative quality values must be clamped to 1 (48 kbps)."
    )
    assert ffmpeg_audio_utils.quality_to_bitrate_kbps("mp3", 999) == 320, (
        "Quality values > 100 must be clamped to 100 (320 kbps)."
    )


@pytest.mark.parametrize(
    ("fmt", "quality", "channels", "expected_tokens"),
    [
        ("mp3", None, 2, ["-c:a", "libmp3lame", "-b:a", "192k"]),
        ("mp3", 50, 2, ["-c:a", "libmp3lame", "-b:a", "183k"]),
        ("m4a", None, 2, ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]),
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
    args = ffmpeg_audio_utils.get_audio_codec_args(
        fmt, quality=quality, channels=channels
    )
    assert args == expected_tokens, (
        f"Codec args mismatch for format='{fmt}', quality={quality}, channels={channels}: "
        f"got {args}, expected {expected_tokens}."
    )


def test_get_audio_codec_args_rejects_unknown_format():
    """`get_audio_codec_args` must raise ValueError for unsupported target formats."""
    with pytest.raises(ValueError, match="Unsupported target audio format"):
        ffmpeg_audio_utils.get_audio_codec_args("wma")


def test_parse_progress_line_tracks_time_and_speed():
    """`_parse_progress_line` must accumulate `out_time` and `speed` and emit on `progress=`."""
    state = ffmpeg_audio_utils._ProgressState()

    assert ffmpeg_audio_utils._parse_progress_line("out_time_us=1500000", state) is False
    assert state.out_time == pytest.approx(1.5), (
        f"Expected out_time=1.5s from out_time_us=1500000, got {state.out_time}."
    )

    assert ffmpeg_audio_utils._parse_progress_line("speed=12.5x", state) is False
    assert state.speed == pytest.approx(12.5), (
        f"Expected speed=12.5 from '12.5x', got {state.speed}."
    )

    assert ffmpeg_audio_utils._parse_progress_line("progress=continue", state) is True


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

    monkeypatch.setattr(ffmpeg_audio_utils.subprocess, "Popen", _fake_popen)

    progress_ticks: list[tuple[float, float, float]] = []
    used = ffmpeg_audio_utils.run_audio_strategies(
        strategies=[
            ("primary", ["primary_cmd"]),
            ("rescue", ["rescue_cmd"]),
        ],
        output_path=output_path,
        display_name="broken.wav",
        progress_callback=lambda t, fps, spd: progress_ticks.append((t, fps, spd)),
    )

    assert used == "rescue", (
        f"Expected fallback strategy 'rescue' to succeed after primary failed, got {used!r}."
    )
    assert attempts == ["primary_cmd", "rescue_cmd"], (
        f"Expected both strategies to be attempted in order, got {attempts}."
    )
    assert output_path.read_bytes() == b"valid-audio-bytes", (
        "Partial output from failed first strategy was not replaced by successful rescue output."
    )
    assert progress_ticks and progress_ticks[-1][1] == 0.0, (
        f"Expected audio progress callback to report fps=0.0, got {progress_ticks}."
    )


def test_run_audio_strategies_raises_interrupted_error_when_cancelled(tmp_path: Path):
    """`run_audio_strategies` must abort immediately with `InterruptedError` if `cancel_event` is set."""
    cancel = threading.Event()
    cancel.set()
    out = tmp_path / "cancelled.mp3"

    with pytest.raises(InterruptedError, match="CANCELLED_BY_USER"):
        ffmpeg_audio_utils.run_audio_strategies(
            strategies=[("primary", ["ffmpeg"])],
            output_path=out,
            display_name="track.wav",
            cancel_event=cancel,
        )


# ---------------------------------------------------------------------------
# 5. Single File Conversion (`src/audio/audio_file_conversion.py`)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("target_fmt", AUDIO_TARGET_FORMATS)
def test_file_converter_converts_wav_to_all_target_formats(
    sample_audio_factory, tmp_path: Path, target_fmt: str
):
    """Real FFmpeg conversion from WAV must succeed and produce a playable audio stream for all target formats."""
    src = sample_audio_factory("source.wav", duration=1.0)
    dst = tmp_path / "converted" / f"source.{target_fmt}"
    progress_calls: list[tuple[float, float, float, float]] = []

    ok = audio_file_conversion.file_converter(
        input_path=src,
        output_path=dst,
        target_format=target_fmt,
        file_progress_callback=lambda d, p, f, s: progress_calls.append((d, p, f, s)),
    )

    assert ok is True, f"Conversion from WAV to '{target_fmt}' unexpectedly returned False."
    assert dst.exists() and dst.stat().st_size > 0, (
        f"Converted file '{dst}' was not created or is empty."
    )

    probed = ffmpeg_audio_utils.probe_audio_streams(
        binary_manager.get_ffmpeg_path(), dst
    )
    assert probed.audio_codecs, (
        f"Probing converted '{dst.name}' found no audio stream."
    )
    if target_fmt != "wav":
        assert progress_calls, (
            f"Expected progress callback to be invoked during WAV -> '{target_fmt}' conversion."
        )


def test_file_converter_bypasses_reencoding_when_extensions_match(
    sample_audio_factory, tmp_path: Path, monkeypatch
):
    """When input extension equals target format, `file_converter` must copy atomically without transcoding."""
    src = sample_audio_factory("already.mp3", duration=1.0, bitrate="128k")
    dst = tmp_path / "out" / "already.mp3"

    def _forbid_strategies(*args, **kwargs):
        raise AssertionError(
            "run_audio_strategies must NOT be called when input and target formats already match."
        )

    monkeypatch.setattr(
        audio_file_conversion, "run_audio_strategies", _forbid_strategies
    )

    ok = audio_file_conversion.file_converter(
        input_path=src,
        output_path=dst,
        target_format="mp3",
    )

    assert ok is True, "Same-format bypass conversion returned False."
    assert dst.read_bytes() == src.read_bytes(), (
        "Same-format bypass must preserve exact source bytes via atomic copy."
    )


def test_file_converter_strips_cover_art_and_converts_audio(
    sample_audio_factory, tmp_path: Path
):
    """Audio files with embedded cover art (`attached_pic`) must convert cleanly without failing on `-vn`."""
    src = sample_audio_factory("with_cover.mp3", duration=1.0, with_cover_art=True)
    dst = tmp_path / "out" / "clean.ogg"

    ok = audio_file_conversion.file_converter(
        input_path=src,
        output_path=dst,
        target_format="ogg",
    )

    assert ok is True, (
        "Conversion of MP3 containing embedded cover art failed; `-vn` mapping should isolate audio."
    )
    assert dst.exists() and dst.stat().st_size > 0, (
        "Output OGG file from cover-art MP3 is missing or empty."
    )


def test_file_converter_rejects_invalid_inputs_safely(
    sample_audio_factory, tmp_path: Path
):
    """`file_converter` must return False on missing, empty, same-path, or corrupted files."""
    missing = tmp_path / "missing.wav"
    assert (
        audio_file_conversion.file_converter(missing, tmp_path / "o.mp3", "mp3")
        is False
    ), "Missing source file must return False."

    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")
    assert (
        audio_file_conversion.file_converter(empty, tmp_path / "o.mp3", "mp3")
        is False
    ), "Zero-byte source file must return False."

    valid = sample_audio_factory("valid.wav", duration=0.5)
    assert (
        audio_file_conversion.file_converter(valid, valid, "mp3") is False
    ), "Refusing to overwrite the source file when input_path == output_path."

    corrupt = tmp_path / "corrupt.mp3"
    corrupt.write_bytes(b"not-a-valid-audio-stream-at-all")
    assert (
        audio_file_conversion.file_converter(corrupt, tmp_path / "o.ogg", "ogg")
        is False
    ), "Corrupted file without probeable audio streams must return False."


def test_file_converter_cleans_temp_file_on_cancellation(
    sample_audio_factory, tmp_path: Path
):
    """Pre-set `cancel_event` must raise `InterruptedError` and leave zero `.tmp` files behind."""
    src = sample_audio_factory("cancel_me.wav", duration=1.0)
    out_dir = tmp_path / "out"
    dst = out_dir / "cancel_me.mp3"
    cancel = threading.Event()
    cancel.set()

    with pytest.raises(InterruptedError):
        audio_file_conversion.file_converter(
            input_path=src,
            output_path=dst,
            target_format="mp3",
            cancel_event=cancel,
        )

    assert not dst.exists(), "Cancelled conversion must not produce final output file."
    leftover_tmps = list(out_dir.glob(".*_tmp_*")) if out_dir.exists() else []
    assert not leftover_tmps, (
        f"Cancelled conversion left temporary files behind: {leftover_tmps}."
    )


# ---------------------------------------------------------------------------
# 6. Single File Compression (`src/audio/audio_file_compression.py`)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ext", ["mp3", "m4a", "ogg", "opus"])
def test_file_compressor_reduces_size_for_lossy_formats(
    sample_audio_factory, tmp_path: Path, ext: str
):
    """Compressing high-bitrate stereo lossy audio at low quality must yield a smaller valid file."""
    high_bitrate = "192k" if ext == "opus" else "320k"
    src = sample_audio_factory(
        f"high.{ext}", duration=2.0, bitrate=high_bitrate, channels=2
    )
    dst = tmp_path / "compressed" / f"high.{ext}"

    ok = audio_file_compression.file_compressor(
        input_path=src,
        output_path=dst,
        quality=15,
    )

    assert ok is True, f"Compression of '{src.name}' at quality=15 returned False."
    assert dst.exists() and dst.stat().st_size > 0, (
        f"Compressed output '{dst}' was not created or is empty."
    )
    assert dst.stat().st_size < src.stat().st_size, (
        f"Expected compressed '{ext}' ({dst.stat().st_size} B) to be smaller than "
        f"source ({src.stat().st_size} B)."
    )


def test_file_compressor_handles_mono_ogg_at_max_quality_without_vorbis_error(
    sample_audio_factory, tmp_path: Path
):
    """Mono OGG compressed at quality=100 must succeed via the 256 kbps channel-aware cap."""
    src = sample_audio_factory(
        "mono_voice.ogg", duration=1.5, bitrate="192k", channels=1
    )
    dst = tmp_path / "compressed" / "mono_voice.ogg"

    ok = audio_file_compression.file_compressor(
        input_path=src,
        output_path=dst,
        quality=100,
    )

    assert ok is True, (
        "Mono OGG compression at quality=100 failed; libvorbis mono cap (256 kbps) should prevent error -22."
    )
    assert dst.exists() and dst.stat().st_size > 0, (
        "Output file for mono OGG compression is missing or empty."
    )


@pytest.mark.parametrize("ext", ["wav", "flac", "aac", "aiff"])
def test_file_compressor_copies_uncompressible_formats_atomically(
    sample_audio_factory, tmp_path: Path, ext: str, monkeypatch
):
    """Formats in `UNCOMPRESSIBLE_AUDIO_FORMATS` must be copied untouched without calling FFmpeg transcode."""
    src = sample_audio_factory(f"lossless.{ext}", duration=0.8)
    dst = tmp_path / "compressed" / f"lossless.{ext}"

    def _forbid_strategies(*args, **kwargs):
        raise AssertionError(
            f"run_audio_strategies must NOT be called for uncompressible format '{ext.upper()}'."
        )

    monkeypatch.setattr(
        audio_file_compression, "run_audio_strategies", _forbid_strategies
    )

    ok = audio_file_compression.file_compressor(
        input_path=src,
        output_path=dst,
        quality=50,
    )

    assert ok is True, f"Uncompressible format '{ext}' should succeed via atomic copy."
    assert dst.read_bytes() == src.read_bytes(), (
        f"Uncompressible format '{ext}' must preserve exact source bytes."
    )


def test_file_compressor_keeps_original_when_compressed_is_not_smaller(
    sample_audio_factory, tmp_path: Path
):
    """If re-encoding at high quality produces a larger file, the original file must be preserved."""
    src = sample_audio_factory("already_tiny.mp3", duration=1.5, bitrate="48k")
    dst = tmp_path / "compressed" / "already_tiny.mp3"

    ok = audio_file_compression.file_compressor(
        input_path=src,
        output_path=dst,
        quality=100,
    )

    assert ok is True, "Compression fallback to original file must return True."
    assert dst.read_bytes() == src.read_bytes(), (
        "When compressed output >= original size, destination must match original bytes exactly."
    )


def test_file_compressor_rejects_invalid_and_handles_cancellation(
    sample_audio_factory, tmp_path: Path
):
    """`file_compressor` must validate paths/streams and clean up temp files on cancellation."""
    valid = sample_audio_factory("source.mp3", duration=1.0, bitrate="192k")

    assert (
        audio_file_compression.file_compressor(valid, valid, quality=50) is False
    ), "Compressor must refuse overwriting source file when input_path == output_path."

    assert (
        audio_file_compression.file_compressor(
            tmp_path / "ghost.mp3", tmp_path / "out.mp3", quality=50
        )
        is False
    ), "Compressor must return False for missing input file."

    cancel = threading.Event()
    cancel.set()
    out_dir = tmp_path / "cancel_out"
    with pytest.raises(InterruptedError):
        audio_file_compression.file_compressor(
            input_path=valid,
            output_path=out_dir / "source.mp3",
            quality=50,
            cancel_event=cancel,
        )

    leftover_tmps = list(out_dir.glob(".*_tmp_*")) if out_dir.exists() else []
    assert not leftover_tmps, (
        f"Cancelled compression left temporary files behind: {leftover_tmps}."
    )


# ---------------------------------------------------------------------------
# 7. Directory Batch Conversion & Compression
# ---------------------------------------------------------------------------


def test_directory_converter_preserves_hierarchy_and_handles_name_collisions(
    sample_audio_factory, tmp_path: Path
):
    """`directory_converter` must preserve folder hierarchy, isolate bad files, and avoid collisions."""
    in_dir = tmp_path / "input"
    out_dir = tmp_path / "output"

    sample_audio_factory("input/song.wav", duration=0.8)
    sample_audio_factory("input/song.flac", duration=0.8)  # same stem -> collision test
    sample_audio_factory("input/album/track01.ogg", duration=0.8)
    (in_dir / "broken.mp3").write_bytes(b"corrupted-audio")

    progress_events = []
    stats = audio_directory_conversion.directory_converter(
        input_dir=in_dir,
        output_dir=out_dir,
        target_format="mp3",
        progress_callback=progress_events.append,
    )

    assert stats["total_files"] == 4, (
        f"Expected 4 scanned audio files, got {stats['total_files']}."
    )
    assert stats["success"] == 3, (
        f"Expected 3 successful conversions, got {stats['success']} (stats={stats})."
    )
    assert stats["failed"] == 1, (
        f"Expected 1 failed conversion for corrupted file, got {stats['failed']}."
    )

    session_dir = out_dir / "converted"
    converted_mp3s = sorted(session_dir.rglob("*.mp3"))
    assert len(converted_mp3s) == 3, (
        f"Expected 3 unique converted MP3 files in '{session_dir}', got {converted_mp3s}."
    )
    assert (session_dir / "album" / "track01_converted.mp3").exists(), (
        "Subdirectory structure 'album/' was not preserved during batch conversion."
    )
    assert any(p.is_completed for p in progress_events), (
        "Expected `progress_callback` to emit completed ProgressInfo events."
    )


def test_directory_compressor_preserves_hierarchy_and_formats(
    sample_audio_factory, tmp_path: Path
):
    """`directory_compressor` must compress lossy files, copy lossless ones, and keep folder structure."""
    in_dir = tmp_path / "input"
    out_dir = tmp_path / "output"

    src_mp3 = sample_audio_factory("input/podcast.mp3", duration=2.0, bitrate="320k")
    src_wav = sample_audio_factory("input/sub/master.wav", duration=0.8)

    stats = audio_directory_compression.directory_compressor(
        input_dir=in_dir,
        output_dir=out_dir,
        quality=20,
    )

    assert stats["total_files"] == 2 and stats["success"] == 2 and stats["failed"] == 0, (
        f"Expected 2/2 successful batch compressions, got stats={stats}."
    )

    session_dir = out_dir / "compressed"
    dst_mp3 = session_dir / "podcast.mp3"
    dst_wav = session_dir / "sub" / "master.wav"

    assert dst_mp3.exists() and dst_mp3.stat().st_size < src_mp3.stat().st_size, (
        "Batch compressor did not reduce size of high-bitrate MP3 file."
    )
    assert dst_wav.exists() and dst_wav.read_bytes() == src_wav.read_bytes(), (
        "Batch compressor did not preserve untouched bytes for lossless WAV file."
    )


def test_directory_operations_handle_empty_dir_and_cancellation(
    sample_audio_factory, tmp_path: Path
):
    """Empty directories must return `no_files=True`, and cancellation must clean up session files."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    out_dir = tmp_path / "out"

    empty_stats = audio_directory_conversion.directory_converter(
        input_dir=empty_dir,
        output_dir=out_dir,
        target_format="mp3",
    )
    assert empty_stats.get("no_files") is True and empty_stats["total_files"] == 0, (
        f"Expected `no_files=True` for empty directory, got {empty_stats}."
    )

    in_dir = tmp_path / "batch_cancel"
    sample_audio_factory("batch_cancel/a.wav", duration=0.8)
    sample_audio_factory("batch_cancel/b.wav", duration=0.8)

    cancel = threading.Event()

    def _cancel_after_first(info):
        if info.is_completed and info.current == 1:
            cancel.set()

    cancel_stats = audio_directory_compression.directory_compressor(
        input_dir=in_dir,
        output_dir=out_dir,
        quality=50,
        progress_callback=_cancel_after_first,
        cancel_event=cancel,
    )

    assert cancel_stats["cancelled"] is True, (
        f"Expected `cancelled=True` when cancel_event triggered mid-batch, got {cancel_stats}."
    )
    assert cancel_stats["cleaned_files_count"] == 1, (
        f"Expected 1 previously created session file to be cleaned up, got {cancel_stats}."
    )
    assert not (out_dir / "compressed").exists(), (
        "Expected empty session directory 'compressed' to be removed after cancellation cleanup."
    )


# ---------------------------------------------------------------------------
# 8. Extended Edge Cases: Bitrate Curve, Sample Rates, Multichannel & Rescue
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ext", ["mp3", "m4a", "opus"])
def test_file_compressor_monotonic_size_across_quality_curve(
    sample_audio_factory, tmp_path: Path, ext: str
):
    """Higher quality values (20 < 60 < 95) must produce strictly larger files on lossy encoders."""
    src = sample_audio_factory(
        f"master_{ext}.wav", duration=2.5, channels=2
    )
    high_src = tmp_path / f"source_high.{ext}"
    assert (
        audio_file_conversion.file_converter(src, high_src, target_format=ext)
        is True
    ), f"Failed to prepare baseline '{ext}' file for quality curve test."

    sizes: dict[int, int] = {}
    for q in (20, 60, 95):
        out = tmp_path / f"out_q{q}.{ext}"
        ok = audio_file_compression.file_compressor(
            input_path=high_src,
            output_path=out,
            quality=q,
        )
        assert ok is True, f"Compression failed for '{ext}' at quality={q}."
        sizes[q] = out.stat().st_size

    assert sizes[20] < sizes[60] <= sizes[95], (
        f"Expected compressed file sizes for '{ext}' to grow with quality "
        f"(q20 < q60 <= q95), got {sizes}."
    )


@pytest.mark.parametrize("sample_rate", [22050, 48000, 96000])
def test_file_converter_handles_non_standard_sample_rates(
    tmp_path: Path, sample_rate: int
):
    """Conversion must succeed cleanly across low (22.05 kHz) and high-res (96 kHz) sample rates."""
    ffmpeg_bin = binary_manager.get_ffmpeg_path()
    src = tmp_path / f"tone_{sample_rate}.wav"
    subprocess.run(
        [
            str(ffmpeg_bin),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:sample_rate={sample_rate}:duration=1.0",
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(src),
        ],
        check=True,
    )

    dst = tmp_path / f"converted_{sample_rate}.opus"
    ok = audio_file_conversion.file_converter(
        input_path=src,
        output_path=dst,
        target_format="opus",
    )

    assert ok is True, (
        f"Conversion from {sample_rate} Hz WAV to Opus unexpectedly failed."
    )
    probed = ffmpeg_audio_utils.probe_audio_streams(ffmpeg_bin, dst)
    assert probed.primary_codec == "opus" and probed.sample_rate == 48000, (
        f"Expected Opus output resampled to 48000 Hz from {sample_rate} Hz source, "
        f"got codec={probed.primary_codec!r}, sample_rate={probed.sample_rate}."
    )


def test_file_converter_and_compressor_trigger_rescue_stereo_fallback(
    sample_audio_factory, tmp_path: Path, monkeypatch
):
    """When primary strategy fails, both `file_converter` and `file_compressor` must recover via rescue stereo strategy."""
    ffmpeg_bin = binary_manager.get_ffmpeg_path()
    src = sample_audio_factory("rescue_src.mp3", duration=1.0, bitrate="256k")
    conv_dst = tmp_path / "rescued_conv.ogg"
    comp_dst = tmp_path / "rescued_comp.mp3"

    real_run = ffmpeg_audio_utils.run_audio_strategies

    def _fail_first_strategy(
        strategies, output_path, display_name, cancel_event=None, progress_callback=None
    ):
        assert len(strategies) >= 2, (
            f"Expected at least 2 strategies (primary + rescue), got {[s[0] for s in strategies]}."
        )
        broken_first = [
            ("forced_failure", [str(ffmpeg_bin), "-invalid_flag_to_force_fallback"])
        ]
        return real_run(
            broken_first + strategies[1:],
            output_path,
            display_name,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )

    monkeypatch.setattr(
        audio_file_conversion, "run_audio_strategies", _fail_first_strategy
    )
    monkeypatch.setattr(
        audio_file_compression, "run_audio_strategies", _fail_first_strategy
    )

    assert (
        audio_file_conversion.file_converter(src, conv_dst, target_format="ogg")
        is True
    ), "file_converter did not recover using the rescue stereo transcode strategy."
    assert conv_dst.exists() and conv_dst.stat().st_size > 0, (
        "Rescue conversion did not produce a non-empty output file."
    )

    assert (
        audio_file_compression.file_compressor(src, comp_dst, quality=30)
        is True
    ), "file_compressor did not recover using the rescue stereo compression strategy."
    assert comp_dst.exists() and comp_dst.stat().st_size > 0, (
        "Rescue compression did not produce a non-empty output file."
    )