import logging
import os
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from src.utils.binary_manager import get_ffmpeg_path
from src.utils.cleanup import copy_original_file_atomically
from src.video.utils.video_ffmpeg_utils import (
    HEVC_COMPRESSION_CONTAINERS,
    RESCUE_INPUT_ARGS,
    RESCUE_STREAM_MAP,
    SAFE_STREAM_MAP,
    StreamInfo,
    base_command,
    container_flags,
    copy_compatibility,
    get_codec_args,
    has_encoder,
    is_same_file,
    probe_streams,
    run_strategies,
)

# Setup module logger
logger = logging.getLogger(__name__)

ResolutionPreset = Literal["1080p", "720p", "480p"]

RESOLUTION_PRESETS: dict[str, int] = {
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
}


def resolve_target_height(resolution: str | int) -> int:
    """Converts a preset label ('1080p', '720p', '480p') or integer into a validated even target height."""
    if isinstance(resolution, int):
        target = resolution
    else:
        key = resolution.strip().lower()
        if key in RESOLUTION_PRESETS:
            target = RESOLUTION_PRESETS[key]
        else:
            cleaned = key.removesuffix("p")
            try:
                target = int(cleaned)
            except ValueError as exc:
                raise ValueError(f"Unsupported target resolution: {resolution!r}") from exc

    if target < 2:
        raise ValueError(f"Target resolution must be >= 2px, got {target}")

    # Guarantee even dimensions for H.264/HEVC chroma subsampling compatibility
    return target - (target % 2)


def build_downscale_filter(
    target_height: int,
    is_10bit: bool = False,
    keep_hevc: bool = False,
) -> list[str]:
    """Builds FFmpeg `-vf` and `-pix_fmt` arguments for aspect-ratio-safe downscaling.

    Handles both landscape (`iw >= ih`) and portrait (`iw < ih`) orientations by
    anchoring the shorter edge to `target_height` and computing the longer edge
    with `-2` so both dimensions are strictly divisible by 2. Never upscales sources
    whose shorter edge is already at or below `target_height`.
    """
    width_expr = f"if(gt(min(iw\\,ih)\\,{target_height})\\,if(gte(iw\\,ih)\\,-2\\,{target_height})\\,trunc(iw/2)*2)"
    height_expr = f"if(gt(min(iw\\,ih)\\,{target_height})\\,if(gte(iw\\,ih)\\,{target_height}\\,-2)\\,trunc(ih/2)*2)"

    target_pix_fmt = "yuv420p10le" if (is_10bit and keep_hevc) else "yuv420p"
    return [
        "-vf",
        f"scale='{width_expr}':'{height_expr}'",
        "-pix_fmt",
        target_pix_fmt,
    ]


def should_skip_downscale(
    info: StreamInfo,
    target_height: int,
) -> bool:
    """Returns True if the video is already at or below `target_height`."""
    if info.width is None or info.height is None:
        return False
    if info.width <= 0 or info.height <= 0:
        return False
    return min(info.width, info.height) <= target_height


def _build_strategies(
    ffmpeg_bin: Path,
    input_path: Path,
    tmp_path: Path,
    target_fmt: str,
    target_height: int,
    video_codec: str | None,
    audio_ok: bool,
    has_audio: bool,
    is_10bit: bool = False,
) -> list[tuple[str, list[str]]]:
    """Builds the ordered (label, command) downscaling strategies targeting a temporary output file."""
    base = base_command(ffmpeg_bin, input_path)
    out = [str(tmp_path)]
    flags = container_flags(target_fmt)

    keep_hevc = (
        video_codec == "hevc"
        and target_fmt in HEVC_COMPRESSION_CONTAINERS
        and has_encoder(ffmpeg_bin, "libx265")
    )
    codec_video_arg = "hevc" if keep_hevc else video_codec
    codec_args = get_codec_args(target_fmt, quality=80, video_codec=codec_video_arg)
    default_codecs = get_codec_args(target_fmt, quality=80, video_codec="h264")

    hevc_tag = (
        ["-tag:v", "hvc1"]
        if video_codec == "hevc" and target_fmt in ("mp4", "mov")
        else []
    )
    encode_flags = (hevc_tag if keep_hevc else []) + flags

    scale_filter = build_downscale_filter(
        target_height=target_height,
        is_10bit=is_10bit,
        keep_hevc=keep_hevc,
    )
    safe_scale_filter = build_downscale_filter(
        target_height=target_height,
        is_10bit=False,
        keep_hevc=False,
    )

    strategies: list[tuple[str, list[str]]] = []

    if audio_ok and has_audio and "-c:a" in codec_args:
        ca_idx = codec_args.index("-c:a")
        audio_copy_codecs = codec_args[:ca_idx] + ["-c:a", "copy"]
        strategies.append(
            (
                "downscale (audio copy)",
                base
                + SAFE_STREAM_MAP
                + scale_filter
                + audio_copy_codecs
                + encode_flags
                + out,
            )
        )

    strategies.append(
        (
            "downscale (safe re-encode)",
            base + SAFE_STREAM_MAP + scale_filter + codec_args + encode_flags + out,
        )
    )

    rescue = base_command(ffmpeg_bin, input_path, RESCUE_INPUT_ARGS) + RESCUE_STREAM_MAP
    strategies.append(
        (
            "rescue downscale",
            rescue
            + safe_scale_filter
            + ["-ac", "2"]
            + default_codecs
            + flags
            + out,
        )
    )
    return strategies


def file_downscaler(
    input_path: Path,
    output_path: Path,
    resolution: str | int = "1080p",
    cancel_event: threading.Event | None = None,
    file_progress_callback: Callable[[float, float, float, float], None] | None = None,
) -> bool:
    """Downscales a video file to the specified target resolution using FFmpeg.

    Preserves aspect ratio for both landscape and portrait videos, keeps dimensions
    divisible by 2 for H.264/HEVC compatibility, and leaves the source file untouched.
    Videos already at or below the target resolution are copied atomically without
    upscaling or re-encoding.
    """
    tmp_path: Path | None = None
    try:
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("CANCELLED_BY_USER")

        if not input_path.exists() or input_path.stat().st_size == 0:
            logger.error(
                f"Refusing to downscale '{input_path.name}': file does not exist or is empty."
            )
            return False

        if is_same_file(input_path, output_path):
            logger.error(
                f"Refusing to downscale '{input_path.name}': output path is the source file."
            )
            return False

        target_height = resolve_target_height(resolution)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        ffmpeg_bin = get_ffmpeg_path()
        info = probe_streams(ffmpeg_bin, input_path)

        if info.video_codec is None:
            logger.error(
                f"Failed to probe video stream for '{input_path.name}': corrupted or unsupported file."
            )
            return False

        if should_skip_downscale(info, target_height):
            copied = copy_original_file_atomically(
                input_path,
                output_path,
                f"already <= {target_height}p ({info.width}x{info.height}), skipping upscale",
            )
            if copied and file_progress_callback and info.duration_seconds > 0.0:
                file_progress_callback(
                    info.duration_seconds, info.duration_seconds, 0.0, 0.0
                )
            return copied

        target_fmt = output_path.suffix.lower().lstrip(".") or "mp4"
        _, audio_ok = copy_compatibility(target_fmt, info)

        logger.info(
            f"Downscaling '{input_path.name}' ({info.width}x{info.height}) to {target_height}p: "
            f"video={info.video_codec}, audio={info.audio_codecs}, is_10bit={info.is_10bit}"
        )

        with tempfile.NamedTemporaryFile(
            dir=output_path.parent,
            prefix=f".{output_path.stem}_tmp_",
            suffix=output_path.suffix,
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)

        strategies = _build_strategies(
            ffmpeg_bin=ffmpeg_bin,
            input_path=input_path,
            tmp_path=tmp_path,
            target_fmt=target_fmt,
            target_height=target_height,
            video_codec=info.video_codec,
            audio_ok=audio_ok,
            has_audio=bool(info.audio_codecs),
            is_10bit=info.is_10bit,
        )

        def _inner_progress(out_time: float, fps: float, speed: float) -> None:
            if file_progress_callback:
                file_progress_callback(info.duration_seconds, out_time, fps, speed)

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
            f"Successfully downscaled '{input_path.name}' to {target_height}p."
        )
        return True

    except InterruptedError:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise

    except Exception:
        logger.exception(f"Failed to downscale '{input_path.name}'.")
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return False
