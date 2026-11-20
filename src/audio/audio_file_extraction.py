import logging
import os
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

from src.audio.utils.audio_ffmpeg_utils import (
    RESCUE_INPUT_ARGS,
    SAFE_AUDIO_MAP,
    base_command,
    get_audio_codec_args,
    is_same_file,
    probe_audio_streams,
    run_audio_strategies,
)
from src.utils.binary_manager import get_ffmpeg_path

logger = logging.getLogger(__name__)


def _build_strategies(
    ffmpeg_bin: Path,
    input_path: Path,
    tmp_path: Path,
    target_fmt: str,
) -> list[tuple[str, list[str]]]:
    """Builds ordered (label, command) strategies targeting a temporary audio file."""
    out = [str(tmp_path)]
    codec_args = get_audio_codec_args(target_fmt, quality=None)

    strategies: list[tuple[str, list[str]]] = [
        (
            "standard audio extraction",
            base_command(ffmpeg_bin, input_path) + SAFE_AUDIO_MAP + codec_args + out,
        ),
        (
            "rescue stereo extraction",
            base_command(ffmpeg_bin, input_path, RESCUE_INPUT_ARGS)
            + SAFE_AUDIO_MAP
            + ["-ac", "2"]
            + codec_args
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
) -> bool:
    """Extracts the primary audio track from a single video file into target_format.

    Strips video, subtitle, and data streams (`-map 0:a:0 -vn`) and encodes
    directly into the chosen audio format in a single FFmpeg pass. Safely
    aborts and returns False if the source video contains no audio stream.

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

    Returns:
        bool: True if audio extraction succeeded, False otherwise.

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
            return False

        if is_same_file(input_path, output_path):
            logger.error(
                f"Refusing to extract audio from '{input_path.name}': "
                "output path is the source file."
            )
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)
        target_fmt = target_format.lower().lstrip(".")

        ffmpeg_bin = get_ffmpeg_path()
        info = probe_audio_streams(ffmpeg_bin, input_path)

        if not info.audio_codecs:
            logger.warning(
                f"Skipping '{input_path.name}': video contains no audio stream."
            )
            return False

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
            return False

        os.replace(tmp_path, output_path)

        logger.info(
            f"Successfully extracted audio from '{input_path.name}' to '{target_fmt}'."
        )
        return True

    except InterruptedError:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise

    except Exception:
        logger.exception(f"Failed to extract audio from '{input_path.name}'.")
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return False
