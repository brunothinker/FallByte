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
    SAFE_VIDEO_FILTER,
    base_command,
    container_flags,
    get_codec_args,
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
    target_ext: str,
    quality: int,
    video_codec: str | None = None,
    hevc_available: bool = False,
) -> list[tuple[str, list[str]]]:
    """Builds the ordered (label, command) strategies for a compression targeting a temporary file.

    HEVC sources going into mp4/mov/mkv stay HEVC (libx265) when the encoder is
    available, with a final libx264 strategy as safety net. Every other source
    follows the original libx264/VP9/WMV2 path unchanged.
    """
    out = [str(tmp_path)]
    keep_hevc = (
        video_codec == "hevc"
        and hevc_available
        and target_ext in HEVC_COMPRESSION_CONTAINERS
    )
    codec_args = get_codec_args(
        target_ext, quality, "hevc" if keep_hevc else None
    )
    hevc_tag = (
        ["-tag:v", "hvc1"] if keep_hevc and target_ext in ("mp4", "mov") else []
    )
    flags = container_flags(target_ext) + hevc_tag

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

    # Safety net: if libx265 fails for any reason, fall back to the original H.264 path.
    if keep_hevc:
        strategies.append(
            (
                "h264 fallback",
                base_command(ffmpeg_bin, input_path)
                + SAFE_STREAM_MAP
                + SAFE_VIDEO_FILTER
                + get_codec_args(target_ext, quality)
                + container_flags(target_ext)
                + out,
            )
        )
    return strategies


def file_compressor(
    input_path: Path,
    output_path: Path,
    quality: int = 80,
    cancel_event: threading.Event | None = None,
    file_progress_callback: Callable[[float, float, float, float], None] | None = None,
) -> bool:
    """Compresses a single video file while strictly maintaining its original format.

    Maps the percentage quality scale (1-100) to the encoder's quality
    parameter (CRF for H.264/VP9, qscale for WMV). If the first strategy fails
    (unusual pixel format, odd dimensions, extra streams, broken timestamps),
    progressively more tolerant strategies are tried. If the result is not
    smaller than the original, the original file is kept as the output.

    Writes output atomically to a temporary file preserving real extension, moving
    it into place via os.replace to ensure pre-existing files are never corrupted.

    Args:
        input_path (Path): Path to the source video file.
        output_path (Path): Path where the compressed video will be saved.
        quality (int, optional): Quality level percentage (1-100). Higher is
          better quality. Defaults to 80.
        cancel_event (threading.Event, optional): Event that, when set,
          terminates the running FFmpeg process. Defaults to None.
        file_progress_callback (Callable[[float, float, float, float], None], optional):
          Callback receiving (duration_seconds, processed_seconds, fps, speed).

    Returns:
        bool: True if compression succeeded, False otherwise.

    Raises:
        InterruptedError: If cancellation was requested via cancel_event.
    """
    tmp_path = None
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

        with tempfile.NamedTemporaryFile(
            dir=output_path.parent,
            prefix=f".{output_path.stem}_tmp_",
            suffix=output_path.suffix,
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)

        info = probe_streams(ffmpeg_bin, input_path)
        hevc_available = (
            info.video_codec == "hevc"
            and target_ext in HEVC_COMPRESSION_CONTAINERS
            and has_encoder(ffmpeg_bin, "libx265")
        )

        strategies = _build_strategies(
            ffmpeg_bin,
            input_path,
            tmp_path,
            target_ext,
            quality,
            info.video_codec,
            hevc_available,
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

        original_size = input_path.stat().st_size
        output_size = tmp_path.stat().st_size
        if output_size >= original_size:
            tmp_path.unlink(missing_ok=True)
            return copy_original_file_atomically(
                input_path,
                output_path,
                f"could not be made smaller at {quality}% quality",
            )
        else:
            os.replace(tmp_path, output_path)
            logger.info(
                f"Successfully compressed '{input_path.name}' "
                f"[Format: {input_path.suffix.upper()} | Quality: {quality}%]."
            )
        return True

    except InterruptedError:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise

    except Exception as e:
        logger.error(
            f"Failed to compress '{input_path.name}': {e}", exc_info=True
        )
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return False