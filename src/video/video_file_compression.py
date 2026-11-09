import logging
import shutil
import threading
from pathlib import Path

from src.video.utils.binary_manager import get_ffmpeg_path
from src.video.utils.ffmpeg_utils import (
    RESCUE_INPUT_ARGS,
    RESCUE_STREAM_MAP,
    SAFE_STREAM_MAP,
    SAFE_VIDEO_FILTER,
    base_command,
    container_flags,
    get_codec_args,
    is_same_file,
    run_strategies,
)

# Setup module logger
logger = logging.getLogger(__name__)


def _build_strategies(
    ffmpeg_bin: Path,
    input_path: Path,
    output_path: Path,
    target_ext: str,
    quality: int,
) -> list[tuple[str, list[str]]]:
    """Builds the ordered (label, command) strategies for a compression."""
    out = [str(output_path)]
    codec_args = get_codec_args(target_ext, quality)
    flags = container_flags(target_ext)

    strategies: list[tuple[str, list[str]]] = []

    # Matroska can carry any subtitle format, so keep them on the first try.
    if target_ext == "mkv":
        strategies.append(
            (
                "re-encode keeping subtitles",
                base_command(ffmpeg_bin, input_path)
                + ["-map", "0:V:0", "-map", "0:a?", "-map", "0:s?", "-c:s", "copy", "-dn"]
                + SAFE_VIDEO_FILTER
                + codec_args
                + out,
            )
        )

    strategies.append(
        (
            "safe re-encode",
            base_command(ffmpeg_bin, input_path)
            + SAFE_STREAM_MAP
            + SAFE_VIDEO_FILTER
            + codec_args
            + flags
            + out,
        )
    )

    # Rescue mode for damaged files / odd timestamps / exotic audio layouts.
    strategies.append(
        (
            "rescue re-encode",
            base_command(ffmpeg_bin, input_path, RESCUE_INPUT_ARGS)
            + RESCUE_STREAM_MAP
            + SAFE_VIDEO_FILTER
            + ["-ac", "2"]
            + codec_args
            + flags
            + out,
        )
    )
    return strategies


def file_compressor(
    input_path: Path,
    output_path: Path,
    quality: int = 80,
    cancel_event: threading.Event | None = None,
) -> bool:
    """Compresses a single video file while strictly maintaining its original format.

    Maps the percentage quality scale (1-100) to the encoder's quality
    parameter (CRF for H.264/VP9, qscale for WMV). If the first strategy fails
    (unusual pixel format, odd dimensions, extra streams, broken timestamps),
    progressively more tolerant strategies are tried. If the result is not
    smaller than the original, the original file is kept as the output.

    Args:
        input_path (Path): Path to the source video file.
        output_path (Path): Path where the compressed video will be saved.
        quality (int, optional): Quality level percentage (1-100). Higher is
          better quality. Defaults to 80.
        cancel_event (threading.Event, optional): Event that, when set,
          terminates the running FFmpeg process. Defaults to None.

    Returns:
        bool: True if compression succeeded, False otherwise.

    Raises:
        InterruptedError: If cancellation was requested via cancel_event.
    """
    try:
        quality = max(1, min(100, int(quality)))

        if is_same_file(input_path, output_path):
            logger.error(
                f"Refusing to compress '{input_path.name}': output path is the source file."
            )
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)
        target_ext = output_path.suffix.lower().lstrip(".")
        ffmpeg_bin = get_ffmpeg_path()

        strategies = _build_strategies(
            ffmpeg_bin, input_path, output_path, target_ext, quality
        )
        used = run_strategies(
            strategies, output_path, input_path.name, cancel_event
        )
        if used is None:
            return False

        original_size = input_path.stat().st_size
        output_size = output_path.stat().st_size
        if output_size >= original_size:
            shutil.copy2(input_path, output_path)
            logger.info(
                f"'{input_path.name}' could not be made smaller at {quality}% "
                f"quality; original file kept."
            )
        else:
            logger.info(
                f"Successfully compressed '{input_path.name}' "
                f"[Format: {input_path.suffix.upper()} | Quality: {quality}%]."
            )
        return True

    except InterruptedError:
        output_path.unlink(missing_ok=True)
        raise

    except Exception as e:
        logger.error(
            f"Failed to compress '{input_path.name}': {e}", exc_info=True
        )
        output_path.unlink(missing_ok=True)
        return False