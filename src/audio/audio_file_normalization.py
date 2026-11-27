"""EBU R128 two-pass linear loudness normalization engine.

Architecture decision (Issue #97):
`file_normalizer` runs a two-pass EBU R128 measurement + linear gain workflow:
1. Pass 1 (`print_format=json` to `-f null -`) measures true integrated loudness
   (`input_i`), true peak (`input_tp`), loudness range (`input_lra`), gating
   threshold (`input_thresh`), and target offset (`target_offset`), mapping progress
   to the first half of the file (0-50%).
2. Pass 2 injects `measured_I`, `measured_TP`, `measured_LRA`, `measured_thresh`,
   `offset`, and `linear=true` into `loudnorm` so FFmpeg applies uniform linear gain
   without dynamic range compression, mapping progress to 50-100%.
3. If Pass 1 cannot parse valid finite metrics (e.g., completely silent tracks where
   `input_i` is `-inf`), `file_normalizer` automatically falls back to single-pass
   dynamic `loudnorm` so silent or unusual files never fail needlessly.
"""

import json
import logging
import math
import os
import queue
import re
import subprocess
import tempfile
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from src.audio.utils.audio_ffmpeg_utils import (
    CANCEL_POLL_INTERVAL,
    RESCUE_INPUT_ARGS,
    SAFE_AUDIO_MAP,
    STDERR_TAIL_BUFFER_SIZE,
    _active_lock,
    _active_processes,
    _parse_progress_line,
    _ProgressState,
    _subprocess_kwargs,
    _terminate_process,
    base_command,
    get_audio_codec_args,
    is_same_file,
    probe_audio_streams,
    run_audio_strategies,
)
from src.formats import NORMALIZABLE_AUDIO_FORMATS
from src.utils.binary_manager import get_ffmpeg_path
from src.utils.cleanup import copy_original_file_atomically
from src.utils.file_result import FileResult

logger = logging.getLogger(__name__)

_LOUDNORM_JSON_RE = re.compile(r'\{[^{}]*"input_i"[^{}]*\}', re.DOTALL)


@dataclass(frozen=True)
class LoudnessPreset:
    """EBU R128 loudness normalization target parameters."""

    key: str
    integrated_lufs: float
    true_peak_dbtp: float
    lra: float

    def to_filter_arg(self) -> str:
        """Builds the single-pass or Pass-1 FFmpeg `loudnorm` filter argument string."""
        return (
            f"loudnorm=I={self.integrated_lufs:.1f}"
            f":TP={self.true_peak_dbtp:.1f}"
            f":LRA={self.lra:.1f}"
        )


@dataclass(frozen=True)
class LoudnormMeasurement:
    """Measured EBU R128 loudness statistics extracted from Pass 1 JSON output."""

    input_i: float
    input_tp: float
    input_lra: float
    input_thresh: float
    target_offset: float

    def to_linear_filter_arg(self, preset: LoudnessPreset) -> str:
        """Builds the Pass-2 linear `loudnorm` filter string with measured parameters."""
        return (
            f"loudnorm=I={preset.integrated_lufs:.1f}"
            f":TP={preset.true_peak_dbtp:.1f}"
            f":LRA={preset.lra:.1f}"
            f":measured_I={self.input_i:.2f}"
            f":measured_TP={self.input_tp:.2f}"
            f":measured_LRA={self.input_lra:.2f}"
            f":measured_thresh={self.input_thresh:.2f}"
            f":offset={self.target_offset:.2f}"
            f":linear=true"
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


@dataclass(frozen=True)
class Pass1Result:
    """Outcome of Pass-1 EBU R128 loudness measurement."""

    measurement: LoudnormMeasurement | None = None
    is_silent: bool = False


def parse_loudnorm_json(stderr_text: str) -> LoudnormMeasurement | None:
    """Parses Pass-1 `loudnorm` JSON diagnostics from FFmpeg stderr.

    Returns None when no valid JSON block is found or when any measured metric
    is non-finite (`-inf`, `inf`, `nan`, e.g., completely silent tracks).
    """
    return inspect_loudnorm_json(stderr_text).measurement


def inspect_loudnorm_json(stderr_text: str) -> Pass1Result:
    """Parses Pass-1 `loudnorm` JSON diagnostics and detects completely silent tracks."""
    matches = _LOUDNORM_JSON_RE.findall(stderr_text)
    if not matches:
        return Pass1Result()

    try:
        payload = json.loads(matches[-1])
        input_i = float(payload["input_i"])
        input_tp = float(payload["input_tp"])
        input_lra = float(payload["input_lra"])
        input_thresh = float(payload["input_thresh"])
        target_offset = float(payload["target_offset"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return Pass1Result()

    if math.isinf(input_i) and input_i < 0:
        return Pass1Result(measurement=None, is_silent=True)

    values = (input_i, input_tp, input_lra, input_thresh, target_offset)
    if not all(math.isfinite(v) for v in values):
        return Pass1Result()

    return Pass1Result(
        measurement=LoudnormMeasurement(
            input_i=input_i,
            input_tp=input_tp,
            input_lra=input_lra,
            input_thresh=input_thresh,
            target_offset=target_offset,
        ),
        is_silent=False,
    )


def _measure_loudnorm_pass(
    ffmpeg_bin: Path,
    input_path: Path,
    preset: LoudnessPreset,
    cancel_event: threading.Event | None = None,
    progress_callback: Callable[[float, float, float], None] | None = None,
) -> Pass1Result:
    """Runs Pass 1 (`print_format=json` -> `-f null -`) and returns parsed EBU R128 stats."""
    if cancel_event is not None and cancel_event.is_set():
        raise InterruptedError("CANCELLED_BY_USER")

    pass1_filter = f"{preset.to_filter_arg()}:print_format=json"
    cmd = (
        base_command(ffmpeg_bin, input_path)
        + SAFE_AUDIO_MAP
        + ["-af", pass1_filter, "-f", "null", "-"]
    )

    process = cast(
        "subprocess.Popen[bytes]",
        subprocess.Popen(cmd, **_subprocess_kwargs()),
    )
    dummy_path = input_path.parent / f".{input_path.stem}_pass1_null"
    with _active_lock:
        _active_processes[process] = dummy_path

    stderr_lines: deque[str] = deque(maxlen=STDERR_TAIL_BUFFER_SIZE)
    stdout_queue: queue.Queue[bytes | None] = queue.Queue()

    def _read_stderr(proc=process, lines=stderr_lines) -> None:
        if proc.stderr:
            for raw_err in iter(proc.stderr.readline, b""):
                lines.append(raw_err.decode("utf-8", errors="ignore"))

    def _read_stdout(proc=process, line_q=stdout_queue) -> None:
        try:
            if proc.stdout:
                for raw_out in iter(proc.stdout.readline, b""):
                    line_q.put(raw_out)
        finally:
            line_q.put(None)

    stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
    stdout_thread = threading.Thread(target=_read_stdout, daemon=True)
    stderr_thread.start()
    stdout_thread.start()

    progress_state = _ProgressState()

    try:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                _terminate_process(process)
                raise InterruptedError("CANCELLED_BY_USER")

            try:
                raw_line = stdout_queue.get(timeout=CANCEL_POLL_INTERVAL)
            except queue.Empty:
                continue

            if raw_line is None:
                break

            decoded_line = raw_line.decode("utf-8", errors="ignore")
            if (
                _parse_progress_line(decoded_line, progress_state)
                and progress_callback
            ):
                progress_callback(progress_state.out_time, 0.0, progress_state.speed)

        process.wait()
        stdout_thread.join(timeout=1.0)
        stderr_thread.join(timeout=1.0)

    except BaseException:
        if process.poll() is None:
            _terminate_process(process)
        stdout_thread.join(timeout=1.0)
        stderr_thread.join(timeout=1.0)
        raise

    finally:
        with _active_lock:
            _active_processes.pop(process, None)

    if process.returncode != 0:
        return Pass1Result()

    if progress_callback:
        progress_callback(progress_state.out_time, 0.0, progress_state.speed)

    return inspect_loudnorm_json("".join(stderr_lines))


def _build_strategies(
    ffmpeg_bin: Path,
    input_path: Path,
    tmp_path: Path,
    target_fmt: str,
    preset: LoudnessPreset,
    channels: int,
    sample_rate: int,
    source_bitrate_kbps: int | None = None,
    measurement: LoudnormMeasurement | None = None,
) -> list[tuple[str, list[str]]]:
    """Builds ordered (label, command) strategies applying EBU R128 `loudnorm`."""
    out = [str(tmp_path)]
    filter_expr = (
        measurement.to_linear_filter_arg(preset)
        if measurement is not None
        else preset.to_filter_arg()
    )
    filter_args = ["-af", filter_expr]
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

    mode_label = "linear loudnorm" if measurement is not None else "single-pass loudnorm"

    return [
        (
            f"standard {mode_label}",
            base_command(ffmpeg_bin, input_path)
            + SAFE_AUDIO_MAP
            + filter_args
            + rate_args
            + codec_args
            + out,
        ),
        (
            f"rescue stereo {mode_label}",
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
    """Normalizes perceived loudness of an audio file using two-pass EBU R128 `loudnorm`.

    Measures integrated loudness, true peak, LRA, and threshold in Pass 1 and applies
    linear gain (`linear=true`) in Pass 2, splitting progress evenly (0-50% / 50-100%).
    Automatically falls back to single-pass dynamic normalization if Pass 1 yields
    non-finite metrics (such as silent files). Preserves the source file's format and
    bitrate and writes output atomically via temporary file + `os.replace`.

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

        def _pass1_progress(out_time: float, fps: float, speed: float) -> None:
            if file_progress_callback:
                half_processed = min(info.duration_seconds * 0.5, out_time * 0.5)
                file_progress_callback(info.duration_seconds, half_processed, fps, speed)

        pass1 = _measure_loudnorm_pass(
            ffmpeg_bin=ffmpeg_bin,
            input_path=input_path,
            preset=preset,
            cancel_event=cancel_event,
            progress_callback=_pass1_progress,
        )
        if pass1.is_silent:
            return copy_original_file_atomically(
                input_path,
                output_path,
                "skip_silent_audio",
            )

        measurement = pass1.measurement
        if measurement is None:
            logger.info(
                f"Pass-1 loudness measurement unavailable for '{input_path.name}'; "
                "falling back to single-pass normalization."
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
            preset=preset,
            channels=info.channels,
            sample_rate=info.sample_rate,
            source_bitrate_kbps=info.bitrate_kbps,
            measurement=measurement,
        )

        def _pass2_progress(out_time: float, fps: float, speed: float) -> None:
            if file_progress_callback:
                base_offset = info.duration_seconds * 0.5
                scaled_processed = min(
                    info.duration_seconds, base_offset + (out_time * 0.5)
                )
                file_progress_callback(
                    info.duration_seconds, scaled_processed, fps, speed
                )

        used = run_audio_strategies(
            strategies,
            tmp_path,
            input_path.name,
            cancel_event,
            progress_callback=_pass2_progress,
        )
        if used is None:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            return FileResult.failed()

        os.replace(tmp_path, output_path)

        mode_desc = "two-pass linear" if measurement is not None else "single-pass"
        logger.info(
            f"Successfully normalized '{input_path.name}' ({mode_desc}) using preset "
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
