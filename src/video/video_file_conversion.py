import logging
import os
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

from src.utils.cleanup import copy_original_file_atomically
from src.video.utils.binary_manager import get_ffmpeg_path
from src.video.utils.ffmpeg_utils import (
    HEVC_COMPRESSION_CONTAINERS,
    RESCUE_INPUT_ARGS,
    RESCUE_STREAM_MAP,
    SAFE_STREAM_MAP,
    base_command,
    container_flags,
    copy_compatibility,
    get_codec_args,
    get_video_filter,
    has_encoder,
    is_same_file,
    probe_streams,
    run_strategies,
)

# Setup module logger
logger = logging.getLogger(__name__)


def _build_strategies(
    ffmpeg_bin: Path,
    input_path: Path,
    tmp_path: Path,
    target_fmt: str,
    video_codec: str | None,
    video_ok: bool,
    audio_ok: bool,
    is_10bit: bool = False,
) -> list[tuple[str, list[str]]]:
    """Builds the ordered (label, command) strategies targeting a temporary output file."""
    base = base_command(ffmpeg_bin, input_path)
    out = [str(tmp_path)]
    flags = container_flags(target_fmt)

    keep_hevc = (
        video_codec == "hevc"
        and target_fmt in HEVC_COMPRESSION_CONTAINERS
        and has_encoder(ffmpeg_bin, "libx265")
    )
    if keep_hevc:
        # Use libx265 to preserve 10-bit HEVC during conversion when possible
        codec_args = [
            "-c:v", "libx265", "-preset", "fast",
            "-c:a", "aac",
        ]
    else:
        codec_args = get_codec_args(target_fmt)
    hevc_tag = (
        ["-tag:v", "hvc1"]
        if keep_hevc and target_fmt in ("mp4", "mov")
        else []
    )
    video_filter = get_video_filter(is_10bit=is_10bit, keep_hevc=keep_hevc)

    strategies: list[tuple[str, list[str]]] = []

    # 1. Pure remux: instant and lossless.
    if target_fmt == "mkv":
        # Matroska accepts everything: try keeping all streams first.
        strategies.append(
            ("remux (all streams)", base + ["-map", "0", "-c", "copy"] + out)
        )
    if video_ok and audio_ok:
        strategies.append(
            ("remux", base + SAFE_STREAM_MAP + ["-c", "copy"] + hevc_tag + flags + out)
        )
    # 2. Keep the video untouched, re-encode only the incompatible audio.
    elif video_ok:
        audio_codec = "libopus" if target_fmt == "webm" else "aac"
        strategies.append(
            (
                "video copy + audio re-encode",
                base
                + SAFE_STREAM_MAP
                + ["-c:v", "copy", "-c:a", audio_codec]
                + hevc_tag
                + flags
                + out,
            )
        )

    # 3. Full re-encode with safe mapping, pixel format and even dimensions.
    strategies.append(
        (
            "safe re-encode",
            base + SAFE_STREAM_MAP + video_filter + codec_args + flags + out,
        )
    )

    # 4. Rescue mode for damaged files / odd timestamps / exotic audio layouts.
    strategies.append(
        (
            "rescue re-encode",
            base_command(ffmpeg_bin, input_path, RESCUE_INPUT_ARGS)
            + RESCUE_STREAM_MAP
            + video_filter
            + ["-ac", "2"]
            + codec_args
            + flags
            + out,
        )
    )
    return strategies


def file_converter(
    input_path: Path,
    output_path: Path,
    target_format: str,
    cancel_event: threading.Event | None = None,
    file_progress_callback: Callable[[float, float, float, float], None] | None = None,
) -> bool:
    """Converts a video file to the specified target format using FFmpeg.

    Tries a chain of strategies, from fastest/lossless to most tolerant, and
    stops at the first one that succeeds:

    1. Remux (stream copy) when the source codecs fit the target container.
    2. Copy the video and re-encode only the audio when just audio is incompatible.
    3. Full re-encode with safe stream mapping, pixel format and even dimensions.
    4. Rescue re-encode (regenerated timestamps, ignored decode errors,
       main video + first audio track only).

    If the input file is already in the target format, it is copied directly.

    Writes output atomically to a temporary file preserving real extension, moving
    it into place via os.replace to ensure pre-existing files are never corrupted.

    Args:
        input_path (Path): Path to the source video file.
        output_path (Path): Path where the converted video will be saved.
        target_format (str): Desired output extension/format (e.g., 'mp4',
          'mkv', 'webm', 'mov', 'avi', 'wmv').
        cancel_event (threading.Event, optional): Event that, when set,
          terminates the running FFmpeg process. Defaults to None.
        file_progress_callback (Callable[[float, float, float, float], None], optional):
          Callback receiving (duration_seconds, processed_seconds, fps, speed).

    Returns:
        bool: True if conversion succeeded, False otherwise.

    Raises:
        InterruptedError: If cancellation was requested via cancel_event.
    """
    tmp_path = None
    try:
        if not input_path.exists() or input_path.stat().st_size == 0:
            logger.error(
                f"Refusing to convert '{input_path.name}': file does not exist or is empty."
            )
            return False

        if is_same_file(input_path, output_path):
            logger.error(
                f"Refusing to convert '{input_path.name}': output path is the source file."
            )
            return False

        # Ensure the destination directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        input_ext = input_path.suffix.lower().lstrip(".")
        target_fmt = target_format.lower().lstrip(".")

        ffmpeg_bin = get_ffmpeg_path()
        info = probe_streams(ffmpeg_bin, input_path)

        # Ensure the media stream is valid before attempting bypass or conversion
        if info.video_codec is None and not info.audio_codecs:
            logger.error(
                f"Failed to probe media streams for '{input_path.name}': corrupted or unsupported file."
            )
            return False

        # Bypass FFmpeg re-encoding if extensions match and media streams are valid
        if input_ext == target_fmt:
            return copy_original_file_atomically(
                input_path,
                output_path,
                f"already .{target_fmt}, skipping re-encoding",
            )

        video_ok, audio_ok = copy_compatibility(target_fmt, info)
        logger.info(
            f"Detected streams for '{input_path.name}': video={info.video_codec}, "
            f"audio={info.audio_codecs}, standard_pix_fmt={info.standard_pix_fmt}, "
            f"is_10bit={info.is_10bit}"
        )

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
            info.video_codec,
            video_ok,
            audio_ok,
            info.is_10bit,
        )

        def _inner_progress(out_time: float, fps: float, speed: float) -> None:
            if file_progress_callback:
                file_progress_callback(
                    info.duration_seconds, out_time, fps, speed
                )

        used = run_strategies(
            strategies,
            tmp_path,
            input_path.name,
            cancel_event,
            progress_callback=_inner_progress,
        )
        if used is None:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            return False

        os.replace(tmp_path, output_path)

        logger.info(
            f"Successfully converted '{input_path.name}' to '{target_fmt}'."
        )
        return True

    except InterruptedError:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise

    except Exception:
        logger.exception(f"Failed to convert '{input_path.name}'.")
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return False