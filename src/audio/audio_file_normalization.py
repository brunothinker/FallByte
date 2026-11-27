import logging
import os
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
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
from src.formats import NORMALIZABLE_AUDIO_FORMATS
from src.utils.binary_manager import get_ffmpeg_path
from src.utils.file_result import FileResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoudnessPreset:
    """EBU R128 loudness normalization target parameters."""

    key: str
    integrated_lufs: float
    true_peak_dbtp: float
    lra: float

    def to_filter_arg(self) -> str:
        """Builds the FFmpeg `loudnorm` filter argument string."""
        return (
            f"loudnorm=I={self.integrated_lufs:.1f}"
            f":TP={self.true_peak_dbtp:.1f}"
            f":LRA={self.lra:.1f}"
        )


LOUDNESS_PRESETS: dict[str, LoudnessPreset] = {
    "music": LoudnessPreset(
        key="music",
        integrated_lufs=-14.0,
        true_peak_dbtp=-1.0,
        lra=11.0,
    ),
    "podcast": LoudnessPreset(
        key="podcast",
        integrated_lufs=-16.0,
        true_peak_dbtp=-1.5,
        lra=7.0,
    ),
    "broadcast": LoudnessPreset(
        key="broadcast",
        integrated_lufs=-23.0,
        true_peak_dbtp=-2.0,
        lra=7.0,
    ),
}

DEFAULT_LOUDNESS_PRESET = "music"


def resolve_loudness_preset(preset_key: str) -> LoudnessPreset:
    """Resolves a preset identifier into its `LoudnessPreset` parameters."""
    normalized = preset_key.strip().lower()
    if normalized not in LOUDNESS_PRESETS:
        raise ValueError(f"Unsupported loudness preset: '{preset_key}'")
    return LOUDNESS_PRESETS[normalized]


def _build_strategies(
    ffmpeg_bin: Path,
    input_path: Path,
    tmp_path: Path,
    target_fmt: str,
    preset: LoudnessPreset,
    channels: int,
    sample_rate: int,
    source_bitrate_kbps: int | None = None,
) -> list[tuple[str, list[str]]]:
    """Builds ordered (label, command) strategies applying EBU R128 `loudnorm`."""
    out = [str(tmp_path)]
    filter_args = ["-af", preset.to_filter_arg()]
    codec_args = get_audio_codec_args(
        target_fmt,
        quality=None,
        channels=channels,
        source_bitrate_kbps=source_bitrate_kbps,
    )

    # FFmpeg's `loudnorm` internally upsamples to 192 kHz; restore source sample rate
    # for formats that do not enforce their own rate (Opus already sets `-ar 48000`).
    rate_args: list[str] = (
        ["-ar", str(sample_rate)]
        if sample_rate > 0 and target_fmt != "opus"
        else []
    )

    rescue_codec_args = get_audio_codec_args(
        target_fmt,
        quality=None,
        channels=2,
        source_bitrate_kbps=source_bitrate_kbps,
    )

    return [
        (
            "standard loudnorm",
            base_command(ffmpeg_bin, input_path)
            + SAFE_AUDIO_MAP
            + filter_args
            + rate_args
            + codec_args
            + out,
        ),
        (
            "rescue stereo loudnorm",
            base_command(ffmpeg_bin, input_path, RESCUE_INPUT_ARGS)
            + SAFE_AUDIO_MAP
            + filter_args
            + ["-ac", "2"]
            + rate_args
            + rescue_codec_args
            + out,
        ),
    ]


def file_normalizer(
    input_path: Path,
    output_path: Path,
    preset_key: str = DEFAULT_LOUDNESS_PRESET,
    cancel_event: threading.Event | None = None,
    file_progress_callback: Callable[[float, float, float, float], None] | None = None,
) -> FileResult:
    """Normalizes perceived loudness of an audio file using FFmpeg's `loudnorm` filter.

    Preserves the source file's audio format and bitrate (when available) and writes
    the normalized output atomically without modifying the original file.

    Args:
        input_path (Path): Path to the source audio file.
        output_path (Path): Path where the normalized audio file will be saved.
        preset_key (str, optional): Target loudness preset key ('music', 'podcast',
            or 'broadcast'). Defaults to 'music' (-14 LUFS).
        cancel_event (threading.Event | None, optional): Event terminating the
            FFmpeg process when set. Defaults to None.
        file_progress_callback (Callable[[float, float, float, float], None] | None, optional):
            Callback receiving (duration_seconds, processed_seconds, fps, speed).
            Defaults to None.

    Returns:
        FileResult: Outcome of the normalization operation.

    Raises:
        InterruptedError: If cancellation was requested via cancel_event.
    """
    tmp_path: Path | None = None
    try:
        if not input_path.exists() or input_path.stat().st_size == 0:
            logger.error(
                f"Refusing to normalize '{input_path.name}': "
                "file does not exist or is empty."
            )
            return FileResult.failed()

        if is_same_file(input_path, output_path):
            logger.error(
                f"Refusing to normalize '{input_path.name}': "
                "output path is the source file."
            )
            return FileResult.failed()

        target_fmt = input_path.suffix.lower().lstrip(".")
        if target_fmt not in NORMALIZABLE_AUDIO_FORMATS:
            logger.warning(
                f"Skipping '{input_path.name}': unsupported format '{target_fmt}' "
                "for loudness normalization."
            )
            return FileResult.skipped(
                "skip_unsupported_normalization_format",
                fmt=target_fmt,
            )

        preset = resolve_loudness_preset(preset_key)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        ffmpeg_bin = get_ffmpeg_path()
        info = probe_audio_streams(ffmpeg_bin, input_path)

        if not info.audio_codecs:
            logger.error(
                f"Refusing to normalize '{input_path.name}': no playable audio stream found."
            )
            return FileResult.failed()

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
            preset=preset,
            channels=info.channels,
            sample_rate=info.sample_rate,
            source_bitrate_kbps=info.bitrate_kbps,
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
            f"Successfully normalized '{input_path.name}' using preset "
            f"'{preset.key}' ({preset.integrated_lufs} LUFS)."
        )
        return FileResult.processed()

    except InterruptedError:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise

    except Exception:
        logger.exception(f"Failed to normalize audio file '{input_path.name}'.")
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return FileResult.failed()
