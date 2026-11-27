"""Dedicated FFmpeg helpers for pure audio conversion and compression.

Completely decoupled from the video engine. Focuses on single primary audio
track extraction/transcoding (`-map 0:a:0 -vn`), safe codec/bitrate mapping,
stream probing, progress parsing, and bounded subprocess execution.
"""

import atexit
import logging
import queue
import re
import subprocess
import sys
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from src.utils.media_tracks import MediaTrack, probe_media_tracks

logger = logging.getLogger(__name__)

# Single primary audio stream, ignoring embedded cover art (-vn), subtitles, and data.
SAFE_AUDIO_MAP: list[str] = ["-map", "0:a:0", "-vn", "-sn", "-dn"]

# Input options that help recover damaged headers or broken timestamps.
RESCUE_INPUT_ARGS: list[str] = ["-fflags", "+genpts", "-err_detect", "ignore_err"]

# Grace period (seconds) before a terminated FFmpeg process is force-killed.
TERMINATE_TIMEOUT = 3.0

# Polling interval (seconds) while waiting for FFmpeg progress lines or cancellation.
CANCEL_POLL_INTERVAL = 0.1

# Maximum trailing stderr lines retained per FFmpeg strategy attempt.
STDERR_TAIL_BUFFER_SIZE = 50

# Quality (1-100) to bitrate (kbps) bounds per lossy target format.
# AAC/M4A enforces a 64 kbps floor so stereo streams avoid severe native encoder artifacts.
BITRATE_RANGES_KBPS: dict[str, tuple[int, int]] = {
    "mp3": (48, 320),
    "m4a": (64, 320),
    "aac": (64, 320),
    "ogg": (48, 320),
    "opus": (32, 192),
}

# libvorbis rejects bitrates above 256 kbps on single-channel (mono) streams.
VORBIS_MONO_MAX_KBPS = 256

_AUDIO_STREAM_RE = re.compile(
    r"Stream #\d+:(\d+)(?:\[[^\]]+\])?(?:\([^)]+\))?:\s*Audio:\s*(\w+)[^,\r\n]*(?:,\s*(\d+)\s*Hz)?,\s*([^,\r\n]+)"
)
_VIDEO_STREAM_RE = re.compile(r"Stream #\d+:\d+.*?: Video:\s*(\w+)")
_DURATION_RE = re.compile(
    r"Duration:\s*(\d{2}):(\d{2}):(\d{2}\.\d+)(?:.*?bitrate:\s*(\d+)\s*kb/s)?"
)
_BITRATE_KBPS_RE = re.compile(r"(\d+)\s*kb/s")


@dataclass
class AudioStreamInfo:
    """Summary of audio streams, bitrate, and duration found in a media file."""

    audio_codecs: list[str] = field(default_factory=list)
    sample_rate: int = 0
    channel_layout: str = ""
    channels: int = 2
    duration_seconds: float = 0.0
    bitrate_kbps: int = 0
    stream_bitrates: dict[int, int] = field(default_factory=dict)

    @property
    def primary_codec(self) -> str | None:
        return self.audio_codecs[0] if self.audio_codecs else None

    def bitrate_for_stream(self, stream_index: int | None = None) -> int:
        """Returns the bitrate (kbps) for `stream_index` if known, else primary bitrate."""
        if (
            stream_index is not None
            and isinstance(self.stream_bitrates, dict)
            and stream_index in self.stream_bitrates
        ):
            return self.stream_bitrates[stream_index]
        return self.bitrate_kbps if isinstance(self.bitrate_kbps, int) else 0


@dataclass
class _ProgressState:
    """Mutable state tracking real-time metrics emitted via `-progress pipe:1`."""

    out_time: float = 0.0
    speed: float = 0.0


def _subprocess_kwargs() -> dict:
    """Common subprocess options: no stdin, captured output, no console flash on Windows."""
    kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


def is_same_file(input_path: Path, output_path: Path) -> bool:
    """True if both paths resolve to the same file (would overwrite the source)."""
    try:
        return input_path.resolve() == output_path.resolve()
    except OSError:
        return False


def base_command(
    ffmpeg_bin: Path, input_path: Path, input_args: list[str] | None = None
) -> list[str]:
    """Builds the common FFmpeg command prefix up to and including the input."""
    return [
        str(ffmpeg_bin),
        "-hide_banner",
        "-nostdin",
        "-progress",
        "pipe:1",
        "-nostats",
        "-y",
        *(input_args or []),
        "-i",
        str(input_path),
    ]


def _infer_channel_count(layout: str) -> int:
    """Infers channel count from FFmpeg channel layout string."""
    normalized = layout.strip().lower()
    if normalized in ("mono", "1 channels", "1.0"):
        return 1
    return 2


def parse_audio_stderr(stderr_text: str) -> AudioStreamInfo:
    """Parses `ffmpeg -i` stderr output into an `AudioStreamInfo` summary."""
    info = AudioStreamInfo()
    container_bitrate_kbps = 0
    has_real_video_stream = False

    for line in stderr_text.splitlines():
        if info.duration_seconds == 0.0:
            dur_match = _DURATION_RE.search(line)
            if dur_match:
                hours, minutes, seconds, container_br = dur_match.groups()
                info.duration_seconds = round(
                    float(hours) * 3600.0 + float(minutes) * 60.0 + float(seconds), 2
                )
                if container_br:
                    container_bitrate_kbps = int(container_br)

        if _VIDEO_STREAM_RE.search(line) and "(attached pic)" not in line.lower():
            has_real_video_stream = True

        match = _AUDIO_STREAM_RE.search(line)
        if not match:
            continue

        stream_idx = int(match.group(1))
        codec = match.group(2).lower()
        sample_rate = int(match.group(3)) if match.group(3) else 0
        layout = match.group(4).strip()

        br_match = _BITRATE_KBPS_RE.search(line)
        stream_br = int(br_match.group(1)) if br_match else 0
        if stream_br > 0:
            info.stream_bitrates[stream_idx] = stream_br

        if not info.audio_codecs:
            info.sample_rate = sample_rate
            info.channel_layout = layout
            info.channels = _infer_channel_count(layout)
            info.bitrate_kbps = stream_br
        info.audio_codecs.append(codec)

    if (
        info.audio_codecs
        and info.bitrate_kbps == 0
        and container_bitrate_kbps > 0
        and not has_real_video_stream
    ):
        info.bitrate_kbps = container_bitrate_kbps

    return info


def probe_audio_streams(ffmpeg_bin: Path, input_path: Path) -> AudioStreamInfo:
    """Probes audio streams, sample rate, channel layout, bitrate, and duration via `ffmpeg -i`.

    Never raises; returns an empty AudioStreamInfo if probing fails.
    """
    try:
        result = subprocess.run(
            [str(ffmpeg_bin), "-hide_banner", "-i", str(input_path)],
            check=False,
            timeout=60,
            **_subprocess_kwargs(),
        )
    except (OSError, subprocess.SubprocessError):
        return AudioStreamInfo()

    stderr_text = result.stderr.decode("utf-8", errors="ignore")
    return parse_audio_stderr(stderr_text)


def probe_audio_tracks(ffmpeg_bin: Path, input_path: Path) -> list[MediaTrack]:
    """Inspects a media file and returns its embedded audio tracks."""
    audio_tracks, _ = probe_media_tracks(ffmpeg_bin, input_path)
    return audio_tracks


def _format_bitrate_bounds(target_fmt: str, channels: int = 2) -> tuple[int, int]:
    """Returns `(min_kbps, max_kbps)` bounds for `target_fmt` and `channels`."""
    fmt = target_fmt.lower().lstrip(".")
    min_kbps, max_kbps = BITRATE_RANGES_KBPS.get(fmt, (48, 320))
    if fmt == "ogg" and channels == 1:
        max_kbps = min(max_kbps, VORBIS_MONO_MAX_KBPS)
    return min_kbps, max_kbps


def quality_to_bitrate_kbps(target_fmt: str, quality: int, channels: int = 2) -> int:
    """Maps a 1-100 quality percentage linearly to a target bitrate in kbps.

    Caps Vorbis (`ogg`) at 256 kbps only when `channels == 1` (mono), keeping
    the full 320 kbps ceiling available for stereo and multi-channel streams.
    """
    clamped = max(1, min(100, int(quality)))
    min_kbps, max_kbps = _format_bitrate_bounds(target_fmt, channels)
    ratio = (clamped - 1) / 99.0
    return round(min_kbps + ratio * (max_kbps - min_kbps))


def _resolve_target_bitrate_kbps(
    target_fmt: str,
    quality: int | None,
    channels: int,
    source_bitrate_kbps: int | None,
    default_kbps: int,
) -> int:
    """Resolves the target bitrate in kbps from quality, source bitrate, or default."""
    if quality is not None:
        return quality_to_bitrate_kbps(target_fmt, quality, channels)

    if (
        isinstance(source_bitrate_kbps, int)
        and not isinstance(source_bitrate_kbps, bool)
        and source_bitrate_kbps > 0
    ):
        min_kbps, max_kbps = _format_bitrate_bounds(target_fmt, channels)
        return max(min_kbps, min(max_kbps, source_bitrate_kbps))

    return default_kbps


def get_audio_codec_args(
    target_fmt: str,
    quality: int | None = None,
    channels: int = 2,
    source_bitrate_kbps: int | None = None,
) -> list[str]:
    """Returns FFmpeg encoder arguments for the target audio format.

    Args:
        target_fmt: Target container/format without leading dot
            ('mp3', 'm4a', 'aac', 'opus', 'ogg', 'flac', 'wav').
        quality: Compression quality (1-100). When None, preserves `source_bitrate_kbps`
            (clamped to the format's allowed bounds) if available, otherwise uses
            high-quality conversion defaults (`192k`, or `128k` for Opus).
        channels: Channel count of the audio stream (1 for mono, >=2 for stereo+).
        source_bitrate_kbps: Optional probed source bitrate in kbps, consulted only
            when `quality is None`. Ignored for lossless targets (`flac`, `wav`).
    """
    fmt = target_fmt.lower().lstrip(".")

    if fmt == "mp3":
        kbps = _resolve_target_bitrate_kbps(
            "mp3", quality, channels, source_bitrate_kbps, 192
        )
        return ["-c:a", "libmp3lame", "-b:a", f"{kbps}k"]

    if fmt == "m4a":
        kbps = _resolve_target_bitrate_kbps(
            "m4a", quality, channels, source_bitrate_kbps, 192
        )
        return ["-c:a", "aac", "-b:a", f"{kbps}k", "-movflags", "+faststart"]

    if fmt == "aac":
        kbps = _resolve_target_bitrate_kbps(
            "aac", quality, channels, source_bitrate_kbps, 192
        )
        return ["-c:a", "aac", "-b:a", f"{kbps}k", "-f", "adts"]

    if fmt == "opus":
        kbps = _resolve_target_bitrate_kbps(
            "opus", quality, channels, source_bitrate_kbps, 128
        )
        # libopus operates natively at 48 kHz and handles resampling cleanly.
        return ["-c:a", "libopus", "-b:a", f"{kbps}k", "-ar", "48000"]

    if fmt == "ogg":
        kbps = _resolve_target_bitrate_kbps(
            "ogg", quality, channels, source_bitrate_kbps, 192
        )
        return ["-c:a", "libvorbis", "-b:a", f"{kbps}k"]

    if fmt == "flac":
        return ["-c:a", "flac", "-compression_level", "5"]

    if fmt == "wav":
        return ["-c:a", "pcm_s16le"]

    raise ValueError(f"Unsupported target audio format: '{target_fmt}'")


# FFmpeg processes currently running, mapped to the output file they write.
_active_processes: dict[subprocess.Popen[bytes], Path] = {}
_active_lock = threading.Lock()


def terminate_active_processes() -> None:
    """Kills every running audio FFmpeg process and removes its partial output file."""
    with _active_lock:
        active = list(_active_processes.items())

    for process, output_path in active:
        if process.poll() is None:
            process.kill()
            process.wait()
        output_path.unlink(missing_ok=True)


atexit.register(terminate_active_processes)


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    """Terminates a running process using wait() to prevent pipe race conditions."""
    process.terminate()
    try:
        process.wait(timeout=TERMINATE_TIMEOUT)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _parse_progress_line(line: str, state: _ProgressState) -> bool:
    """Parses a single `key=value` line from FFmpeg's `-progress pipe:1` output."""
    stripped = line.strip()
    if not stripped or "=" not in stripped:
        return False

    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()

    if key == "out_time_us":
        try:
            state.out_time = float(value) / 1_000_000.0
        except ValueError:
            pass
    elif key == "out_time" and state.out_time == 0.0:
        parts = value.split(":")
        if len(parts) == 3:
            try:
                hours, minutes, seconds = map(float, parts)
                state.out_time = hours * 3600.0 + minutes * 60.0 + seconds
            except ValueError:
                pass
    elif key == "speed":
        cleaned = value.rstrip("xX")
        try:
            state.speed = float(cleaned)
        except ValueError:
            pass
    elif key == "progress":
        return True

    return False


def run_audio_strategies(
    strategies: list[tuple[str, list[str]]],
    output_path: Path,
    display_name: str,
    cancel_event: threading.Event | None = None,
    progress_callback: Callable[[float, float, float], None] | None = None,
) -> str | None:
    """Runs audio FFmpeg strategies in order until one produces a valid output file.

    Decouples stdout pipe reads onto a background reader thread so `cancel_event`
    terminates FFmpeg promptly even when stdout emits no lines.

    Args:
        strategies: Ordered (label, command) pairs to attempt.
        output_path: Destination file produced by the commands.
        display_name: Source file name used in log messages.
        cancel_event: Optional event signaling a user cancellation request.
        progress_callback: Optional callback receiving (processed_seconds, fps, speed).
            `fps` is always reported as `0.0` for pure audio streams.

    Returns:
        str | None: Label of the successful strategy, or None if all failed.

    Raises:
        InterruptedError: If cancellation was requested or raised during callback execution.
    """
    for label, cmd in strategies:
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("CANCELLED_BY_USER")

        process = cast(
            "subprocess.Popen[bytes]",
            subprocess.Popen(cmd, **_subprocess_kwargs()),
        )
        with _active_lock:
            _active_processes[process] = output_path

        stderr_lines: deque[str] = deque(maxlen=STDERR_TAIL_BUFFER_SIZE)
        stdout_queue: queue.Queue[bytes | None] = queue.Queue()

        def _read_stderr(proc=process, lines=stderr_lines) -> None:
            if proc.stderr:
                for raw_err in iter(proc.stderr.readline, b""):
                    lines.append(raw_err.decode("utf-8", errors="ignore"))

        def _read_stdout(proc=process, line_q=stdout_queue) -> None:
            try:
                if proc.stdout:
                    for raw_out in iter(proc.stdout.readline, b""):
                        line_q.put(raw_out)
            finally:
                line_q.put(None)

        stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
        stdout_thread = threading.Thread(target=_read_stdout, daemon=True)
        stderr_thread.start()
        stdout_thread.start()

        progress_state = _ProgressState()

        try:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    _terminate_process(process)
                    output_path.unlink(missing_ok=True)
                    raise InterruptedError("CANCELLED_BY_USER")

                try:
                    raw_line = stdout_queue.get(timeout=CANCEL_POLL_INTERVAL)
                except queue.Empty:
                    continue

                if raw_line is None:
                    break

                decoded_line = raw_line.decode("utf-8", errors="ignore")
                if (
                    _parse_progress_line(decoded_line, progress_state)
                    and progress_callback
                ):
                    progress_callback(
                        progress_state.out_time,
                        0.0,
                        progress_state.speed,
                    )

            process.wait()
            stdout_thread.join(timeout=1.0)
            stderr_thread.join(timeout=1.0)

        except BaseException:
            if process.poll() is None:
                _terminate_process(process)
            output_path.unlink(missing_ok=True)
            stdout_thread.join(timeout=1.0)
            stderr_thread.join(timeout=1.0)
            raise

        finally:
            with _active_lock:
                _active_processes.pop(process, None)

        if (
            process.returncode == 0
            and output_path.exists()
            and output_path.stat().st_size > 0
        ):
            if progress_callback:
                progress_callback(
                    progress_state.out_time,
                    0.0,
                    progress_state.speed,
                )
            logger.info(f"'{display_name}' processed using strategy: {label}.")
            return label

        output_path.unlink(missing_ok=True)
        stderr_tail = "\n".join("".join(stderr_lines).strip().splitlines()[-4:])
        logger.warning(
            f"Audio strategy '{label}' failed for '{display_name}': {stderr_tail}"
        )

    logger.error(f"All audio strategies failed for '{display_name}'.")
    return None
