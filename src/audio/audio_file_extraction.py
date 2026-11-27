import logging
import os
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

from src.audio.utils.audio_ffmpeg_utils import (
    RESCUE_INPUT_ARGS,
    SAFE_AUDIO_MAP,
    MediaTrack,
    base_command,
    get_audio_codec_args,
    is_same_file,
    probe_audio_streams,
    probe_audio_tracks,
    run_audio_strategies,
)
from src.utils.binary_manager import get_ffmpeg_path
from src.utils.file_result import FileResult

logger = logging.getLogger(__name__)


def inspect_audio_tracks(
    input_path: Path,
    ffmpeg_bin: Path | None = None,
) -> list[MediaTrack]:
    """Inspects a single media file and returns its embedded audio tracks."""
    if not input_path.exists() or not input_path.is_file():
        logger.warning(f"Media file not found for audio track inspection: '{input_path}'")
        return []

    resolved_ffmpeg = ffmpeg_bin or get_ffmpeg_path()
    return probe_audio_tracks(resolved_ffmpeg, input_path)


def _resolve_audio_map(stream_index: int | None) -> list[str]:
    """Builds FFmpeg `-map` arguments for either a specific stream index or default primary audio."""
    if stream_index is None:
        return list(SAFE_AUDIO_MAP)
    return ["-map", f"0:{stream_index}", "-vn", "-sn", "-dn"]


def _build_strategies(
    ffmpeg_bin: Path,
    input_path: Path,
    tmp_path: Path,
    target_fmt: str,
    stream_index: int | None = None,
    channels: int = 2,
    source_bitrate_kbps: int | None = None,
) -> list[tuple[str, list[str]]]:
    """Builds ordered (label, command) strategies targeting a temporary audio file."""
    out = [str(tmp_path)]
    codec_args = get_audio_codec_args(
        target_fmt,
        quality=None,
        channels=channels,
        source_bitrate_kbps=source_bitrate_kbps,
    )
    rescue_codec_args = get_audio_codec_args(
        target_fmt,
        quality=None,
        channels=2,
        source_bitrate_kbps=source_bitrate_kbps,
    )
    audio_map = _resolve_audio_map(stream_index)

    strategies: list[tuple[str, list[str]]] = [
        (
            "standard audio extraction",
            base_command(ffmpeg_bin, input_path) + audio_map + codec_args + out,
        ),
        (
            "rescue stereo extraction",
            base_command(ffmpeg_bin, input_path, RESCUE_INPUT_ARGS)
            + audio_map
            + ["-ac", "2"]
            + rescue_codec_args
            + out,
        ),
    ]
    return strategies


def file_extractor(
    input_path: Path,
    output_path: Path,
    target_format: str,
    cancel_event: threading.Event | None = None,
    file_progress_callback: Callable[[float, float, float, float], None] | None = None,
    stream_index: int | None = None,
) -> FileResult:
    """Extracts an audio track from a single video file into target_format.

    Strips video, subtitle, and data streams (`-map 0:a:0 -vn` by default, or
    `-map 0:<stream_index> -vn` when specified) and encodes directly into the
    chosen audio format in a single FFmpeg pass, preserving the source stream's
    bitrate (clamped to the target format's bounds) when available. Safely aborts
    and returns skipped if the source video contains no audio stream.

    Args:
        input_path (Path): Path to the source video file.
        output_path (Path): Path where the extracted audio file will be saved.
        target_format (str): Desired output audio format ('mp3', 'm4a', 'opus',
            'ogg', 'flac', 'wav').
        cancel_event (threading.Event | None, optional): Event terminating the
            FFmpeg process when set. Defaults to None.
        file_progress_callback (Callable[[float, float, float, float], None] | None, optional):
            Callback receiving (duration_seconds, processed_seconds, fps, speed).
            Defaults to None.
        stream_index (int | None, optional): Global stream index to extract
            (e.g. `1` -> `-map 0:1`). Defaults to None (`0:a:0`).

    Returns:
        FileResult: Outcome of the audio extraction operation.

    Raises:
        InterruptedError: If cancellation was requested via cancel_event.
    """
    tmp_path: Path | None = None
    try:
        if not input_path.exists() or input_path.stat().st_size == 0:
            logger.error(
                f"Refusing to extract audio from '{input_path.name}': "
                "file does not exist or is empty."
            )
            return FileResult.failed()

        if is_same_file(input_path, output_path):
            logger.error(
                f"Refusing to extract audio from '{input_path.name}': "
                "output path is the source file."
            )
            return FileResult.failed()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        target_fmt = target_format.lower().lstrip(".")

        ffmpeg_bin = get_ffmpeg_path()
        info = probe_audio_streams(ffmpeg_bin, input_path)

        if not info.audio_codecs:
            logger.warning(
                f"Skipping '{input_path.name}': video contains no audio stream."
            )
            return FileResult.skipped("skip_no_audio_stream")

        with tempfile.NamedTemporaryFile(
            dir=output_path.parent,
            prefix=f".{output_path.stem}_tmp_",
            suffix=output_path.suffix,
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)

        strategies = _build_strategies(
            ffmpeg_bin,
            input_path,
            tmp_path,
            target_fmt,
            stream_index=stream_index,
            channels=info.channels,
            source_bitrate_kbps=info.bitrate_for_stream(stream_index),
        )

        def _inner_progress(out_time: float, fps: float, speed: float) -> None:
            if file_progress_callback:
                file_progress_callback(info.duration_seconds, out_time, fps, speed)

        used = run_audio_strategies(
            strategies,
            tmp_path,
            input_path.name,
            cancel_event,
            progress_callback=_inner_progress,
        )
        if used is None:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            return FileResult.failed()

        os.replace(tmp_path, output_path)

        logger.info(
            f"Successfully extracted audio from '{input_path.name}' to '{target_fmt}'."
        )
        return FileResult.processed()

    except InterruptedError:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise

    except Exception:
        logger.exception(f"Failed to extract audio from '{input_path.name}'.")
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return FileResult.failed()
