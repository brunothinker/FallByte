"""Lossless video track selector (audio & subtitle stream remuxing)."""

import logging
import os
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

from src.utils.binary_manager import get_ffmpeg_path
from src.utils.file_result import FileResult
from src.video.utils.video_ffmpeg_utils import (
    RESCUE_INPUT_ARGS,
    MediaTrack,
    base_command,
    classify_subtitle_codec,
    container_flags,
    is_same_file,
    probe_media_tracks,
    probe_streams,
    run_strategies,
    subtitle_transcode_target,
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


def _prepare_selected_tracks(
    selected_stream_indices: list[int],
    subtitle_tracks: list[MediaTrack],
    target_fmt: str,
    display_name: str,
) -> tuple[list[int], str | None]:
    """Filters incompatible subtitle streams and determines if subtitle transcoding is needed.

    Bitmap subtitles (and any subtitle in containers without subtitle support) are dropped
    with a warning so they do not abort the entire remux job. Text subtitles in containers
    that require re-encoding (e.g. `mov_text` in MP4/MOV or `webvtt` in WebM) trigger a
    subtitle-only re-encode fallback strategy.

    Returns:
        tuple[list[int], str | None]: (compatible_stream_indices, subtitle_transcode_codec)
    """
    subtitle_by_index = {track.stream_index: track for track in subtitle_tracks}
    compatible_indices: list[int] = []
    needs_subtitle_transcode = False

    for stream_idx in selected_stream_indices:
        sub_track = subtitle_by_index.get(stream_idx)
        if sub_track is None:
            compatible_indices.append(stream_idx)
            continue

        disposition = classify_subtitle_codec(target_fmt, sub_track.codec)
        if disposition == "copy":
            compatible_indices.append(stream_idx)
        elif disposition == "transcode":
            compatible_indices.append(stream_idx)
            needs_subtitle_transcode = True
        else:
            logger.warning(
                f"Dropping incompatible subtitle track #{stream_idx} "
                f"(codec='{sub_track.codec}') for target container '.{target_fmt}' "
                f"in '{display_name}'."
            )

    transcode_codec = (
        subtitle_transcode_target(target_fmt) if needs_subtitle_transcode else None
    )
    return compatible_indices, transcode_codec


def _build_remux_strategies(
    ffmpeg_bin: Path,
    input_path: Path,
    output_target: Path,
    map_args: list[str],
    mux_flags: list[str],
    subtitle_transcode_codec: str | None = None,
) -> list[tuple[str, list[str]]]:
    """Builds ordered FFmpeg remux strategies targeting `output_target`."""
    strategies: list[tuple[str, list[str]]] = [
        # Primary strategy: preserve global metadata and selected tracks while disabling
        # chapter track synthesis (`-map_chapters -1`), which otherwise writes a text
        # subtitle/data stream into MP4 containers even when all subtitles are unchecked.
        (
            "lossless_remux_with_metadata",
            [
                *base_command(ffmpeg_bin, input_path),
                *map_args,
                "-map_metadata",
                "0",
                "-map_chapters",
                "-1",
                "-c",
                "copy",
                *mux_flags,
                str(output_target),
            ],
        ),
        # Fallback strategy: omit global metadata copying in case malformed tags block muxing.
        (
            "lossless_remux_minimal",
            [
                *base_command(ffmpeg_bin, input_path),
                *map_args,
                "-map_chapters",
                "-1",
                "-c",
                "copy",
                *mux_flags,
                str(output_target),
            ],
        ),
        # Rescue strategy: regenerate timestamps and ignore stream errors (helpful for .ts/.flv/.mpg).
        (
            "lossless_remux_rescue",
            [
                *base_command(ffmpeg_bin, input_path, input_args=RESCUE_INPUT_ARGS),
                *map_args,
                "-map_chapters",
                "-1",
                "-c",
                "copy",
                *mux_flags,
                str(output_target),
            ],
        ),
    ]

    if subtitle_transcode_codec:
        # Container-specific subtitle transcode fallback (e.g. `-c copy -c:s mov_text` for MP4/MOV):
        # stream-copies video and audio losslessly while re-encoding only text subtitle streams.
        strategies.extend(
            [
                (
                    f"remux_{subtitle_transcode_codec}_with_metadata",
                    [
                        *base_command(ffmpeg_bin, input_path),
                        *map_args,
                        "-map_metadata",
                        "0",
                        "-map_chapters",
                        "-1",
                        "-c",
                        "copy",
                        "-c:s",
                        subtitle_transcode_codec,
                        *mux_flags,
                        str(output_target),
                    ],
                ),
                (
                    f"remux_{subtitle_transcode_codec}_minimal",
                    [
                        *base_command(ffmpeg_bin, input_path),
                        *map_args,
                        "-map_chapters",
                        "-1",
                        "-c",
                        "copy",
                        "-c:s",
                        subtitle_transcode_codec,
                        *mux_flags,
                        str(output_target),
                    ],
                ),
            ]
        )

    return strategies


def remux_selected_tracks(
    input_path: Path,
    output_path: Path,
    selected_stream_indices: list[int],
    cancel_event: threading.Event | None = None,
    progress_callback: Callable[[float, float, float], None] | None = None,
    ffmpeg_bin: Path | None = None,
) -> FileResult:
    """Creates a lossless copy of `input_path` keeping only selected audio/subtitle tracks.

    Writes output atomically to a temporary file next to `output_path` and moves it into
    place via `os.replace` only after FFmpeg succeeds, ensuring pre-existing files are
    never corrupted and no partial output remains on failure or cancellation.

    Args:
        input_path: Source video file.
        output_path: Destination video file (must not resolve to `input_path`).
        selected_stream_indices: Global stream indices (e.g. `[1, 3]`) of audio/subtitle
            tracks to retain. May be empty to strip all audio and subtitle tracks.
        cancel_event: Optional event signaling a user cancellation request.
        progress_callback: Optional callback receiving `(processed_seconds, fps, speed)`.
        ffmpeg_bin: Optional explicit FFmpeg binary path.

    Returns:
        FileResult: Outcome of the track remuxing operation.

    Raises:
        InterruptedError: If cancelled via `cancel_event`.
    """
    tmp_path: Path | None = None
    try:
        if not input_path.exists() or not input_path.is_file():
            logger.error(f"Input video file does not exist: '{input_path}'")
            return FileResult.failed()

        if is_same_file(input_path, output_path):
            logger.error(
                f"Refusing to overwrite source video file in-place: '{input_path}'"
            )
            return FileResult.failed()

        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("CANCELLED_BY_USER")

        resolved_ffmpeg = ffmpeg_bin or get_ffmpeg_path()
        target_fmt = output_path.suffix.lstrip(".").lower()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        stream_info = probe_streams(resolved_ffmpeg, input_path)
        duration = stream_info.duration_seconds
        _, subtitle_tracks = probe_media_tracks(resolved_ffmpeg, input_path)

        compatible_indices, subtitle_transcode_codec = _prepare_selected_tracks(
            selected_stream_indices=selected_stream_indices,
            subtitle_tracks=subtitle_tracks,
            target_fmt=target_fmt,
            display_name=input_path.name,
        )

        def _scaled_progress(processed_sec: float, fps: float, speed: float) -> None:
            if progress_callback is None:
                return
            clamped_sec = min(processed_sec, duration) if duration > 0 else processed_sec
            progress_callback(clamped_sec, fps, speed)

        with tempfile.NamedTemporaryFile(
            dir=output_path.parent,
            prefix=f".{output_path.stem}_tmp_",
            suffix=output_path.suffix,
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)

        map_args = build_track_selection_maps(compatible_indices)
        mux_flags = container_flags(target_fmt)
        strategies = _build_remux_strategies(
            ffmpeg_bin=resolved_ffmpeg,
            input_path=input_path,
            output_target=tmp_path,
            map_args=map_args,
            mux_flags=mux_flags,
            subtitle_transcode_codec=subtitle_transcode_codec,
        )

        used_strategy = run_strategies(
            strategies=strategies,
            output_path=tmp_path,
            display_name=input_path.name,
            cancel_event=cancel_event,
            progress_callback=_scaled_progress if progress_callback else None,
        )
        if used_strategy is None:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            return FileResult.failed()

        os.replace(tmp_path, output_path)
        return FileResult.processed()

    except InterruptedError:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise

    except Exception:
        logger.exception(f"Failed to remux tracks for '{input_path.name}'.")
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return FileResult.failed()
