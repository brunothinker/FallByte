"""Tests for single-file audio conversion (`src/audio/audio_file_conversion.py`)."""

import subprocess
import threading
from pathlib import Path

import pytest

from src.audio import audio_file_compression, audio_file_conversion
from src.audio.utils import audio_ffmpeg_utils
from src.formats import AUDIO_TARGET_FORMATS
from src.utils import binary_manager
from tests.audio.helpers import (
    ALL_TESTABLE_AUDIO_FORMATS,
    requires_libmp3lame,
    requires_libopus,
    requires_libvorbis,
    skip_if_format_encoders_unavailable,
)


@pytest.mark.parametrize("target_fmt", AUDIO_TARGET_FORMATS)
def test_file_converter_converts_wav_to_all_target_formats(
    sample_audio_factory, tmp_path: Path, target_fmt: str
):
    """Real FFmpeg conversion from WAV must succeed and produce a playable audio stream for all target formats."""
    skip_if_format_encoders_unavailable("wav", target_fmt)
    src = sample_audio_factory("source.wav", duration=1.0)
    dst = tmp_path / "converted" / f"source.{target_fmt}"
    progress_calls: list[tuple[float, float, float, float]] = []

    ok = audio_file_conversion.file_converter(
        input_path=src,
        output_path=dst,
        target_format=target_fmt,
        file_progress_callback=lambda d, p, f, s: progress_calls.append((d, p, f, s)),
    )

    assert ok is True, (
        f"[audio] Conversion from WAV to '{target_fmt}' unexpectedly returned False."
    )
    assert dst.exists() and dst.stat().st_size > 0, (
        f"[audio] Converted file '{dst}' was not created or is empty."
    )

    probed = audio_ffmpeg_utils.probe_audio_streams(
        binary_manager.get_ffmpeg_path(), dst
    )
    assert probed.audio_codecs, (
        f"[audio] Probing converted '{dst.name}' found no playable audio stream."
    )
    if target_fmt != "wav":
        assert progress_calls, (
            f"[audio] Expected progress callback to be invoked during WAV -> '{target_fmt}' conversion."
        )


@pytest.mark.parametrize("source_fmt", ALL_TESTABLE_AUDIO_FORMATS)
@pytest.mark.parametrize("target_fmt", AUDIO_TARGET_FORMATS)
def test_file_converter_full_format_matrix(
    sample_audio_factory, tmp_path: Path, source_fmt: str, target_fmt: str
):
    """Every supported source format must convert cleanly into every target format."""
    skip_if_format_encoders_unavailable(source_fmt, target_fmt)

    src = sample_audio_factory(f"matrix_src_{source_fmt}.{source_fmt}", duration=0.6)
    dst = tmp_path / "matrix" / f"{source_fmt}_to_{target_fmt}.{target_fmt}"

    ok = audio_file_conversion.file_converter(
        input_path=src,
        output_path=dst,
        target_format=target_fmt,
    )

    assert ok is True, (
        f"[audio] Matrix conversion '{source_fmt}' -> '{target_fmt}' unexpectedly returned False."
    )
    assert dst.exists() and dst.stat().st_size > 0, (
        f"[audio] Matrix conversion '{source_fmt}' -> '{target_fmt}' produced missing or empty output at '{dst}'."
    )

    probed = audio_ffmpeg_utils.probe_audio_streams(
        binary_manager.get_ffmpeg_path(), dst
    )
    assert probed.audio_codecs, (
        f"[audio] Probing converted '{dst.name}' ({source_fmt} -> {target_fmt}) found no audio stream."
    )


@requires_libmp3lame
def test_file_converter_bypasses_reencoding_when_extensions_match(
    sample_audio_factory, tmp_path: Path, monkeypatch
):
    """When input extension equals target format, `file_converter` must copy atomically without transcoding."""
    src = sample_audio_factory("already.mp3", duration=1.0, bitrate="128k")
    dst = tmp_path / "out" / "already.mp3"

    def _forbid_strategies(*args, **kwargs):
        raise AssertionError(
            "run_audio_strategies must NOT be called when input and target formats already match."
        )

    monkeypatch.setattr(
        audio_file_conversion, "run_audio_strategies", _forbid_strategies
    )

    ok = audio_file_conversion.file_converter(
        input_path=src,
        output_path=dst,
        target_format="mp3",
    )

    assert ok is True, "[audio] Same-format bypass conversion returned False."
    assert dst.read_bytes() == src.read_bytes(), (
        "[audio] Same-format bypass must preserve exact source bytes via atomic copy."
    )


@requires_libmp3lame
@requires_libvorbis
def test_file_converter_strips_cover_art_and_converts_audio(
    sample_audio_factory, tmp_path: Path
):
    """Audio files with embedded cover art (`attached_pic`) must convert cleanly without failing on `-vn`."""
    src = sample_audio_factory("with_cover.mp3", duration=1.0, with_cover_art=True)
    dst = tmp_path / "out" / "clean.ogg"

    ok = audio_file_conversion.file_converter(
        input_path=src,
        output_path=dst,
        target_format="ogg",
    )

    assert ok is True, (
        "[audio] Conversion of MP3 containing embedded cover art failed; `-vn` mapping should isolate audio."
    )
    assert dst.exists() and dst.stat().st_size > 0, (
        "[audio] Output OGG file from cover-art MP3 is missing or empty."
    )


def test_file_converter_rejects_invalid_inputs_safely(
    sample_audio_factory, tmp_path: Path
):
    """`file_converter` must return False on missing, empty, same-path, or corrupted files."""
    missing = tmp_path / "missing.wav"
    assert (
        audio_file_conversion.file_converter(missing, tmp_path / "o.mp3", "mp3")
        is False
    ), "[audio] Missing source file must return False without raising."

    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")
    assert (
        audio_file_conversion.file_converter(empty, tmp_path / "o.mp3", "mp3")
        is False
    ), "[audio] Zero-byte source file must return False."

    valid = sample_audio_factory("valid.wav", duration=0.5)
    assert (
        audio_file_conversion.file_converter(valid, valid, "mp3") is False
    ), "[audio] Converter must refuse to overwrite the source file when input_path == output_path."

    corrupt = tmp_path / "corrupt.mp3"
    corrupt.write_bytes(b"not-a-valid-audio-stream-at-all")
    assert (
        audio_file_conversion.file_converter(corrupt, tmp_path / "o.ogg", "ogg")
        is False
    ), "[audio] Corrupted file without probeable audio streams must return False."


def test_file_converter_cleans_temp_file_on_cancellation(
    sample_audio_factory, tmp_path: Path
):
    """Pre-set `cancel_event` must raise `InterruptedError` and leave zero `.tmp` files behind."""
    src = sample_audio_factory("cancel_me.wav", duration=1.0)
    out_dir = tmp_path / "out"
    dst = out_dir / "cancel_me.mp3"
    cancel = threading.Event()
    cancel.set()

    with pytest.raises(InterruptedError):
        audio_file_conversion.file_converter(
            input_path=src,
            output_path=dst,
            target_format="mp3",
            cancel_event=cancel,
        )

    assert not dst.exists(), (
        "[audio] Cancelled conversion must not leave behind a final output file."
    )
    leftover_tmps = list(out_dir.glob(".*_tmp_*")) if out_dir.exists() else []
    assert not leftover_tmps, (
        f"[audio] Cancelled conversion left temporary files behind: {leftover_tmps}."
    )


@requires_libopus
@pytest.mark.parametrize("sample_rate", [22050, 48000, 96000])
def test_file_converter_handles_non_standard_sample_rates(
    tmp_path: Path, sample_rate: int
):
    """Conversion must succeed cleanly across low (22.05 kHz) and high-res (96 kHz) sample rates."""
    ffmpeg_bin = binary_manager.get_ffmpeg_path()
    src = tmp_path / f"tone_{sample_rate}.wav"
    subprocess.run(
        [
            str(ffmpeg_bin),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:sample_rate={sample_rate}:duration=1.0",
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(src),
        ],
        check=True,
    )

    dst = tmp_path / f"converted_{sample_rate}.opus"
    ok = audio_file_conversion.file_converter(
        input_path=src,
        output_path=dst,
        target_format="opus",
    )

    assert ok is True, (
        f"[audio] Conversion from {sample_rate} Hz WAV to Opus unexpectedly failed."
    )
    probed = audio_ffmpeg_utils.probe_audio_streams(ffmpeg_bin, dst)
    assert probed.primary_codec == "opus" and probed.sample_rate == 48000, (
        f"[audio] Expected Opus output resampled to 48000 Hz from {sample_rate} Hz source, "
        f"got codec={probed.primary_codec!r}, sample_rate={probed.sample_rate}."
    )


@requires_libmp3lame
@requires_libvorbis
def test_file_converter_and_compressor_trigger_rescue_stereo_fallback(
    sample_audio_factory, tmp_path: Path, monkeypatch
):
    """When primary strategy fails, both `file_converter` and `file_compressor` must recover via rescue stereo strategy."""
    ffmpeg_bin = binary_manager.get_ffmpeg_path()
    src = sample_audio_factory("rescue_src.mp3", duration=1.0, bitrate="256k")
    conv_dst = tmp_path / "rescued_conv.ogg"
    comp_dst = tmp_path / "rescued_comp.mp3"

    real_run = audio_ffmpeg_utils.run_audio_strategies

    def _fail_first_strategy(
        strategies, output_path, display_name, cancel_event=None, progress_callback=None
    ):
        assert len(strategies) >= 2, (
            f"[audio] Expected at least 2 strategies (primary + rescue), got {[s[0] for s in strategies]}."
        )
        broken_first = [
            ("forced_failure", [str(ffmpeg_bin), "-invalid_flag_to_force_fallback"])
        ]
        return real_run(
            broken_first + strategies[1:],
            output_path,
            display_name,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )

    monkeypatch.setattr(
        audio_file_conversion, "run_audio_strategies", _fail_first_strategy
    )
    monkeypatch.setattr(
        audio_file_compression, "run_audio_strategies", _fail_first_strategy
    )

    assert (
        audio_file_conversion.file_converter(src, conv_dst, target_format="ogg")
        is True
    ), "[audio] file_converter did not recover using the rescue stereo transcode strategy."
    assert conv_dst.exists() and conv_dst.stat().st_size > 0, (
        "[audio] Rescue conversion did not produce a non-empty output file."
    )

    assert (
        audio_file_compression.file_compressor(src, comp_dst, quality=30)
        is True
    ), "[audio] file_compressor did not recover using the rescue stereo compression strategy."
    assert comp_dst.exists() and comp_dst.stat().st_size > 0, (
        "[audio] Rescue compression did not produce a non-empty output file."
    )