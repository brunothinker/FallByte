import logging
import os
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

from src.audio.utils.binary_manager import get_ffmpeg_path
from src.audio.utils.ffmpeg_audio_utils import (
    RESCUE_INPUT_ARGS,
    SAFE_AUDIO_MAP,
    base_command,
    get_audio_codec_args,
    is_same_file,
    probe_audio_streams,
    run_audio_strategies,
)
from src.formats import UNCOMPRESSIBLE_AUDIO_FORMATS
from src.utils.cleanup import copy_original_file_atomically

logger = logging.getLogger(__name__)


def _build_strategies(
    ffmpeg_bin: Path,
    input_path: Path,
    tmp_path: Path,
    target_ext: str,
    quality: int,
    channels: int = 2,
) -> list[tuple[str, list[str]]]:
    """Builds ordered (label, command) strategies for audio compression."""
    out = [str(tmp_path)]
    primary_codec_args = get_audio_codec_args(
        target_ext, quality=quality, channels=channels
    )
    stereo_codec_args = get_audio_codec_args(
        target_ext, quality=quality, channels=2
    )

    return [
        (
            "standard audio compression",
            base_command(ffmpeg_bin, input_path)
            + SAFE_AUDIO_MAP
            + primary_codec_args
            + out,
        ),
        (
            "rescue stereo compression",
            base_command(ffmpeg_bin, input_path, RESCUE_INPUT_ARGS)
            + SAFE_AUDIO_MAP
            + ["-ac", "2"]
            + stereo_codec_args
            + out,
        ),
    ]


def file_compressor(
    input_path: Path,
    output_path: Path,
    quality: int = 80,
    cancel_event: threading.Event | None = None,
    file_progress_callback: Callable[[float, float, float, float], None] | None = None,
) -> bool:
    """Compresses a single audio file while preserving its original container/format.

    Lossy formats (MP3, M4A, OGG, OPUS) are re-encoded using a bitrate mapped
    from `quality` (1-100). Non-compressible formats (FLAC, WAV, AAC, WMA, AIFF)
    are copied untouched via `copy_original_file_atomically`, matching the image
    compression behavior. If the compressed result is not smaller than the
    original, the original file is kept as the output.

    Args:
        input_path (Path): Path to the source audio file.
        output_path (Path): Destination path where compressed audio will be saved.
        quality (int, optional): Compression quality percentage (1-100). Defaults to 80.
        cancel_event (threading.Event, optional): Event terminating FFmpeg when set.
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

        if not input_path.exists() or input_path.stat().st_size == 0:
            logger.error(
                f"Refusing to compress '{input_path.name}': file does not exist or is empty."
            )
            return False

        if is_same_file(input_path, output_path):
            logger.error(
                f"Refusing to compress '{input_path.name}': output path is the source file."
            )
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)
        target_ext = output_path.suffix.lower().lstrip(".")
        fmt_upper = target_ext.upper()

        ffmpeg_bin = get_ffmpeg_path()
        info = probe_audio_streams(ffmpeg_bin, input_path)

        if not info.audio_codecs:
            logger.error(
                f"Failed to probe audio streams for '{input_path.name}': "
                "no audio track found or file is corrupted."
            )
            return False

        if fmt_upper in UNCOMPRESSIBLE_AUDIO_FORMATS:
            return copy_original_file_atomically(
                input_path,
                output_path,
                f"{fmt_upper} is not re-encoded during audio compression",
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
            target_ext,
            quality,
            channels=info.channels,
        )

        def _inner_progress(out_time: float, fps: float, speed: float) -> None:
            if file_progress_callback:
                file_progress_callback(
                    info.duration_seconds, out_time, fps, speed
                )

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
            return False

        original_size = input_path.stat().st_size
        output_size = tmp_path.stat().st_size
        if output_size >= original_size:
            tmp_path.unlink(missing_ok=True)
            return copy_original_file_atomically(
                input_path,
                output_path,
                f"compressed result was not smaller at {quality}% quality",
            )

        os.replace(tmp_path, output_path)
        logger.info(
            f"Successfully compressed '{input_path.name}' "
            f"[Format: {fmt_upper} | Quality: {quality}%]."
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