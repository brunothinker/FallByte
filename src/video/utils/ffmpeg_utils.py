"""Shared FFmpeg helpers used by the video conversion and compression engines.

Centralizes stream probing, safe stream mapping, per-container codec selection
and the "try strategies until one works" runner, so both engines behave the
same way on unusual files (10-bit, odd dimensions, extra subtitle/data
streams, exotic audio codecs, broken timestamps, etc.).
"""

import atexit
import logging
import re
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

# Setup module logger
logger = logging.getLogger(__name__)

# Codecs that can be stream-copied (no re-encode) into each container.
# None means the container accepts practically anything (Matroska).
COPY_VIDEO_OK: dict[str, set[str] | None] = {
    "mp4": {"h264", "hevc", "mpeg4", "av1", "vp9"},
    "mov": {"h264", "hevc", "mpeg4"},
    "mkv": None,
    "avi": {"h264", "mpeg4"},
    "webm": {"vp8", "vp9", "av1"},
    "wmv": set(),
}
COPY_AUDIO_OK: dict[str, set[str] | None] = {
    "mp4": {"aac", "mp3", "ac3"},
    "mov": {"aac", "mp3", "ac3"},
    "mkv": None,
    "avi": {"aac", "mp3", "ac3"},
    "webm": {"opus", "vorbis"},
    "wmv": set(),
}

# First real video stream (0:V excludes cover art) + every audio stream.
# Subtitles and data streams are dropped because most containers reject them.
SAFE_STREAM_MAP: list[str] = ["-map", "0:V:0", "-map", "0:a?", "-sn", "-dn"]
# Rescue mode keeps only the first audio track.
RESCUE_STREAM_MAP: list[str] = ["-map", "0:V:0", "-map", "0:a:0?", "-sn", "-dn"]
# Even dimensions and the pixel format every player/encoder accepts.
SAFE_VIDEO_FILTER: list[str] = [
    "-vf",
    "scale=trunc(iw/2)*2:trunc(ih/2)*2",
    "-pix_fmt",
    "yuv420p",
]
# Input options that help with damaged files / broken timestamps.
RESCUE_INPUT_ARGS: list[str] = ["-fflags", "+genpts", "-err_detect", "ignore_err"]

# Polling interval (seconds) used to check for cancellation while FFmpeg runs.
CANCEL_POLL_INTERVAL = 0.2
# Grace period (seconds) before a terminated FFmpeg process is force-killed.
TERMINATE_TIMEOUT = 3.0

_STREAM_RE = re.compile(r"Stream #\d+:\d+.*?: (Video|Audio): (\w+)")
_STANDARD_PIX_FMT_RE = re.compile(r"\byuvj?420p\b")


@dataclass
class StreamInfo:
    """Summary of the streams found in a media file."""

    video_codec: str | None = None
    audio_codecs: list[str] = field(default_factory=list)
    standard_pix_fmt: bool = True


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
        "-y",
        *(input_args or []),
        "-i",
        str(input_path),
    ]


def probe_streams(ffmpeg_bin: Path, input_path: Path) -> StreamInfo:
    """Reads main video codec, audio codecs and pixel format via `ffmpeg -i`.

    Cover-art streams (attached pictures) are ignored. Never raises; returns an
    empty StreamInfo if probing fails.
    """
    info = StreamInfo()
    try:
        result = subprocess.run(
            [str(ffmpeg_bin), "-hide_banner", "-i", str(input_path)],
            timeout=60,
            **_subprocess_kwargs(),
        )
    except (OSError, subprocess.SubprocessError):
        return info

    for line in result.stderr.decode("utf-8", errors="ignore").splitlines():
        match = _STREAM_RE.search(line)
        if not match:
            continue
        kind, codec = match.group(1), match.group(2).lower()
        if kind == "Video" and info.video_codec is None and "attached pic" not in line:
            info.video_codec = codec
            info.standard_pix_fmt = bool(_STANDARD_PIX_FMT_RE.search(line))
        elif kind == "Audio":
            info.audio_codecs.append(codec)
    return info


def codec_allowed(allowed: set[str] | None, codecs: list[str]) -> bool:
    """True if every codec is accepted by the container (None accepts all)."""
    if allowed is None:
        return True
    return bool(codecs) and all(c in allowed for c in codecs)


def copy_compatibility(target_fmt: str, info: StreamInfo) -> tuple[bool, bool]:
    """Tells whether video and audio can be stream-copied into the target container.

    Returns:
        tuple[bool, bool]: (video_copyable, audio_copyable)
    """
    video_ok = info.video_codec is not None and codec_allowed(
        COPY_VIDEO_OK.get(target_fmt, set()), [info.video_codec]
    )
    # 10-bit / 4:4:4 / 4:2:2 copied into MP4/MOV/AVI/WebM often won't play.
    if video_ok and target_fmt != "mkv" and not info.standard_pix_fmt:
        video_ok = False

    audio_ok = not info.audio_codecs or codec_allowed(
        COPY_AUDIO_OK.get(target_fmt, set()), info.audio_codecs
    )
    return video_ok, audio_ok


def container_flags(target_fmt: str) -> list[str]:
    """Container-specific muxer flags."""
    if target_fmt in ("mp4", "mov"):
        return ["-movflags", "+faststart"]
    return []


def get_codec_args(target_fmt: str, quality: int | None = None) -> list[str]:
    """Returns encoder arguments for the target container.

    Args:
        target_fmt: Container extension without dot (mp4, mkv, webm, mov, avi, wmv).
        quality: 1-100 quality (compression). None selects conversion defaults.
    """
    if target_fmt == "webm":
        crf = 30 if quality is None else round(15 + (100 - quality) * 0.4)
        return [
            "-c:v", "libvpx-vp9", "-crf", str(crf), "-b:v", "0",
            "-row-mt", "1", "-cpu-used", "4",
            "-c:a", "libopus",
        ]

    if target_fmt == "wmv":
        qscale = 3 if quality is None else round(1 + (100 - quality) * 0.3)
        # WMA encoder only supports mono/stereo.
        return [
            "-c:v", "wmv2", "-qscale:v", str(qscale),
            "-c:a", "wmav2", "-ac", "2",
        ]

    # MP4, MKV, MOV, AVI (and any other container that takes H.264 + AAC)
    if quality is None:
        return ["-c:v", "libx264", "-c:a", "aac"]
    crf = round(18 + (100 - quality) * 0.22)
    return [
        "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
        "-c:a", "aac", "-b:a", "128k",
    ]


# FFmpeg processes currently running, mapped to the output file they write.
_active_processes: dict[subprocess.Popen[bytes], Path] = {}
_active_lock = threading.Lock()


def terminate_active_processes() -> None:
    """Kills every running FFmpeg process and removes its partial output file."""
    with _active_lock:
        active = list(_active_processes.items())

    for process, output_path in active:
        if process.poll() is None:
            process.kill()
            process.wait()
        output_path.unlink(missing_ok=True)


# Prevents orphan FFmpeg processes when the application window is closed.
atexit.register(terminate_active_processes)


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    """Terminates a running process, escalating to kill if it does not exit in time."""
    process.terminate()
    try:
        process.communicate(timeout=TERMINATE_TIMEOUT)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()


def run_strategies(
    strategies: list[tuple[str, list[str]]],
    output_path: Path,
    display_name: str,
    cancel_event: threading.Event | None = None,
) -> str | None:
    """Runs FFmpeg strategies in order until one produces a valid output file.

    Partial outputs from failed attempts are removed before the next attempt.
    If cancel_event is set while FFmpeg is running, the process is terminated
    and the partial output is removed.

    Args:
        strategies: Ordered (label, command) pairs to attempt.
        output_path: Destination file produced by the commands.
        display_name: Source file name used in log messages.
        cancel_event: Optional event signaling a user cancellation request.

    Returns:
        str | None: Label of the successful strategy, or None if all failed.

    Raises:
        InterruptedError: If cancellation was requested.
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

        try:
            while True:
                try:
                    _, stderr_data = process.communicate(
                        timeout=CANCEL_POLL_INTERVAL
                    )
                    break
                except subprocess.TimeoutExpired:
                    if cancel_event is not None and cancel_event.is_set():
                        _terminate_process(process)
                        output_path.unlink(missing_ok=True)
                        raise InterruptedError("CANCELLED_BY_USER")
        finally:
            with _active_lock:
                _active_processes.pop(process, None)

        if (
            process.returncode == 0
            and output_path.exists()
            and output_path.stat().st_size > 0
        ):
            logger.info(f"'{display_name}' processed using strategy: {label}.")
            return label

        output_path.unlink(missing_ok=True)
        stderr_tail = "\n".join(
            (stderr_data or b"").decode("utf-8", errors="ignore").strip().splitlines()[-4:]
        )
        logger.warning(
            f"Strategy '{label}' failed for '{display_name}': {stderr_tail}"
        )

    logger.error(f"All strategies failed for '{display_name}'.")
    return None