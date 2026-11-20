"""Lossless video track selector (audio & subtitle stream remuxing)."""

import logging
import threading
from collections.abc import Callable
from pathlib import Path

from src.utils.binary_manager import get_ffmpeg_path
from src.video.utils.video_ffmpeg_utils import (
    RESCUE_INPUT_ARGS,
    MediaTrack,
    base_command,
    container_flags,
    is_same_file,
    probe_media_tracks,
    probe_streams,
    run_strategies,
)

logger = logging.getLogger(__name__)


def inspect_video_tracks(
    input_path: Path,
    ffmpeg_bin: Path | None = None,
) -> tuple[list[MediaTrack], list[MediaTrack]]:
    """Inspects a single video file and returns its embedded audio and subtitle tracks.

    Args:
        input_path: Path to the source video file.
        ffmpeg_bin: Optional explicit FFmpeg binary path (defaults to bundled binary).

    Returns:
        tuple[list[MediaTrack], list[MediaTrack]]: (audio_tracks, subtitle_tracks)
    """
    if not input_path.exists() or not input_path.is_file():
        logger.warning(f"Video file not found for track inspection: '{input_path}'")
        return [], []

    resolved_ffmpeg = ffmpeg_bin or get_ffmpeg_path()
    return probe_media_tracks(resolved_ffmpeg, input_path)


def build_track_selection_maps(selected_stream_indices: list[int]) -> list[str]:
    """Builds FFmpeg `-map` arguments preserving real video streams and selected tracks.

    Uses `0:V?` (uppercase V with optional flag) to copy real video streams while excluding
    attached cover-art pictures and tolerating audio-only files, followed by explicit
    `0:<index>` mappings in ascending stream order.
    """
    map_args: list[str] = ["-map", "0:V?"]
    for stream_idx in sorted(set(selected_stream_indices)):
        if stream_idx >= 0:
            map_args.extend(["-map", f"0:{stream_idx}"])
    return map_args


def remux_selected_tracks(
    input_path: Path,
    output_path: Path,
    selected_stream_indices: list[int],
    cancel_event: threading.Event | None = None,
    progress_callback: Callable[[float, float, float], None] | None = None,
    ffmpeg_bin: Path | None = None,
) -> bool:
    """Creates a lossless copy of `input_path` keeping only selected audio/subtitle tracks.

    Args:
        input_path: Source video file.
        output_path: Destination video file (must not resolve to `input_path`).
        selected_stream_indices: Global stream indices (e.g. `[1, 3]`) of audio/subtitle
            tracks to retain. May be empty to strip all audio and subtitle tracks.
        cancel_event: Optional event signaling a user cancellation request.
        progress_callback: Optional callback receiving `(processed_seconds, fps, speed)`.
        ffmpeg_bin: Optional explicit FFmpeg binary path.

    Returns:
        bool: True if remuxing succeeded and produced a non-empty file, False otherwise.

    Raises:
        InterruptedError: If cancelled via `cancel_event`.
    """
    if not input_path.exists() or not input_path.is_file():
        logger.error(f"Input video file does not exist: '{input_path}'")
        return False

    if is_same_file(input_path, output_path):
        logger.error(
            f"Refusing to overwrite source video file in-place: '{input_path}'"
        )
        return False

    if cancel_event is not None and cancel_event.is_set():
        raise InterruptedError("CANCELLED_BY_USER")

    resolved_ffmpeg = ffmpeg_bin or get_ffmpeg_path()
    target_fmt = output_path.suffix.lstrip(".").lower()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stream_info = probe_streams(resolved_ffmpeg, input_path)
    duration = stream_info.duration_seconds

    def _scaled_progress(processed_sec: float, fps: float, speed: float) -> None:
        if progress_callback is None:
            return
        clamped_sec = min(processed_sec, duration) if duration > 0 else processed_sec
        progress_callback(clamped_sec, fps, speed)

    map_args = build_track_selection_maps(selected_stream_indices)
    mux_flags = container_flags(target_fmt)

    # Primary strategy: preserve global metadata and selected tracks while disabling
    # chapter track synthesis (`-map_chapters -1`), which otherwise writes a text
    # subtitle/data stream into MP4 containers even when all subtitles are unchecked.
    primary_cmd = [
        *base_command(resolved_ffmpeg, input_path),
        *map_args,
        "-map_metadata",
        "0",
        "-map_chapters",
        "-1",
        "-c",
        "copy",
        *mux_flags,
        str(output_path),
    ]

    # Fallback strategy: omit global metadata copying in case malformed tags block muxing.
    fallback_cmd = [
        *base_command(resolved_ffmpeg, input_path),
        *map_args,
        "-map_chapters",
        "-1",
        "-c",
        "copy",
        *mux_flags,
        str(output_path),
    ]

    # Rescue strategy: regenerate timestamps and ignore stream errors (helpful for .ts/.flv/.mpg).
    rescue_cmd = [
        *base_command(resolved_ffmpeg, input_path, input_args=RESCUE_INPUT_ARGS),
        *map_args,
        "-map_chapters",
        "-1",
        "-c",
        "copy",
        *mux_flags,
        str(output_path),
    ]

    strategies: list[tuple[str, list[str]]] = [
        ("lossless_remux_with_metadata", primary_cmd),
        ("lossless_remux_minimal", fallback_cmd),
        ("lossless_remux_rescue", rescue_cmd),
    ]

    used_strategy = run_strategies(
        strategies=strategies,
        output_path=output_path,
        display_name=input_path.name,
        cancel_event=cancel_event,
        progress_callback=_scaled_progress if progress_callback else None,
    )

    return used_strategy is not None
