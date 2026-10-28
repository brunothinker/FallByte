import logging
import shutil
from pathlib import Path

from src.video.utils.binary_manager import get_ffmpeg_path
from src.video.utils.ffmpeg_utils import (
    RESCUE_INPUT_ARGS,
    RESCUE_STREAM_MAP,
    SAFE_STREAM_MAP,
    SAFE_VIDEO_FILTER,
    base_command,
    container_flags,
    copy_compatibility,
    get_codec_args,
    is_same_file,
    probe_streams,
    run_strategies,
)

# Setup module logger
logger = logging.getLogger(__name__)


def _build_strategies(
    ffmpeg_bin: Path,
    input_path: Path,
    output_path: Path,
    target_fmt: str,
    video_codec: str | None,
    video_ok: bool,
    audio_ok: bool,
) -> list[tuple[str, list[str]]]:
    """Builds the ordered (label, command) strategies for a conversion."""
    base = base_command(ffmpeg_bin, input_path)
    out = [str(output_path)]
    flags = container_flags(target_fmt)
    codec_args = get_codec_args(target_fmt)
    hevc_tag = (
        ["-tag:v", "hvc1"]
        if video_codec == "hevc" and target_fmt in ("mp4", "mov")
        else []
    )

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
            base + SAFE_STREAM_MAP + SAFE_VIDEO_FILTER + codec_args + flags + out,
        )
    )

    # 4. Rescue mode for damaged files / odd timestamps / exotic audio layouts.
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


def file_converter(
    input_path: Path,
    output_path: Path,
    target_format: str,
) -> bool:
    """Converts a video file to the specified target format using FFmpeg.

    Tries a chain of strategies, from fastest/lossless to most tolerant, and
    stops at the first one that succeeds:

    1. Remux (stream copy) when the source codecs fit the target container.
    2. Copy the video and re-encode only the audio when just audio is incompatible.
    3. Full re-encode with safe stream mapping, yuv420p and even dimensions.
    4. Rescue re-encode (regenerated timestamps, ignored decode errors,
       main video + first audio track only).

    If the input file is already in the target format, it is copied directly.

    Args:
        input_path (Path): Path to the source video file.
        output_path (Path): Path where the converted video will be saved.
        target_format (str): Desired output extension/format (e.g., 'mp4',
          'mkv', 'webm', 'mov', 'avi', 'wmv').

    Returns:
        bool: True if conversion succeeded, False otherwise.
    """
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
            logger.info(
                f"Skipping re-encoding for '{input_path.name}': already .{target_fmt}. Copying file..."
            )
            shutil.copy2(input_path, output_path)
            return True

        video_ok, audio_ok = copy_compatibility(target_fmt, info)
        logger.info(
            f"Detected streams for '{input_path.name}': video={info.video_codec}, "
            f"audio={info.audio_codecs}, standard_pix_fmt={info.standard_pix_fmt}"
        )

        strategies = _build_strategies(
            ffmpeg_bin,
            input_path,
            output_path,
            target_fmt,
            info.video_codec,
            video_ok,
            audio_ok,
        )

        used = run_strategies(strategies, output_path, input_path.name)
        if used is None:
            output_path.unlink(missing_ok=True)
            return False

        logger.info(
            f"Successfully converted '{input_path.name}' to '{target_fmt}'."
        )
        return True

    except Exception:
            logger.exception(f"Failed to convert '{input_path.name}'.")
            output_path.unlink(missing_ok=True)
            return False