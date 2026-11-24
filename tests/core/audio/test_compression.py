"""Core (audio): tests from compression."""

import threading
from pathlib import Path

import pytest

from src.audio import (
    audio_directory_compression,
    audio_file_compression,
    audio_file_conversion,
)
from src.audio.utils import audio_ffmpeg_utils
from tests.core.audio.helpers import (
    requires_libmp3lame,
    requires_libvorbis,
    skip_if_format_encoders_unavailable,
)


@requires_libmp3lame
def test_directory_compressor_preserves_hierarchy_and_formats(
    sample_audio_factory, tmp_path: Path
):
    """`directory_compressor` must compress lossy files, copy/skip lossless ones, and keep folder structure."""
    in_dir = tmp_path / "input"
    out_dir = tmp_path / "output"

    src_mp3 = sample_audio_factory("input/podcast.mp3", duration=2.0, bitrate="320k")
    src_wav = sample_audio_factory("input/sub/master.wav", duration=0.8)

    stats = audio_directory_compression.directory_compressor(
        input_dir=in_dir,
        output_dir=out_dir,
        quality=20,
    )

    assert (
        stats["total_files"] == 2
        and stats["success"] == 1
        and stats["skipped"] == 1
        and stats["failed"] == 0
    ), f"[audio] Expected 1 processed + 1 skipped batch compressions, got stats={stats}."

    session_dir = out_dir / "compressed"
    dst_mp3 = session_dir / "podcast.mp3"
    dst_wav = session_dir / "sub" / "master.wav"

    assert dst_mp3.exists() and dst_mp3.stat().st_size < src_mp3.stat().st_size, (
        "[audio] Batch compressor did not reduce size of high-bitrate MP3 file."
    )
    assert dst_wav.exists() and dst_wav.read_bytes() == src_wav.read_bytes(), (
        "[audio] Batch compressor did not preserve untouched bytes for lossless WAV file."
    )


@pytest.mark.parametrize("ext", ["mp3", "m4a", "aac", "ogg", "opus"])
def test_file_compressor_reduces_size_for_lossy_formats(
    sample_audio_factory, tmp_path: Path, ext: str
):
    """Compressing high-bitrate stereo lossy audio at low quality must yield a smaller valid file and report progress."""
    skip_if_format_encoders_unavailable(ext)
    high_bitrate = "192k" if ext == "opus" else "320k"
    src = sample_audio_factory(
        f"high.{ext}", duration=2.0, bitrate=high_bitrate, channels=2
    )
    dst = tmp_path / "compressed" / f"high.{ext}"
    progress_calls: list[tuple[float, float, float, float]] = []

    res = audio_file_compression.file_compressor(
        input_path=src,
        output_path=dst,
        quality=15,
        file_progress_callback=lambda d, p, f, s: progress_calls.append((d, p, f, s)),
    )

    assert res.is_processed, (
        f"[audio] Compression of '{src.name}' at quality=15 unexpectedly failed or skipped: {res}."
    )
    assert dst.exists() and dst.stat().st_size > 0, (
        f"[audio] Compressed output '{dst}' was not created or is empty."
    )
    assert dst.stat().st_size < src.stat().st_size, (
        f"[audio] Expected compressed '{ext}' ({dst.stat().st_size} B) to be smaller than "
        f"source ({src.stat().st_size} B)."
    )
    assert progress_calls, (
        f"[audio] Expected `file_progress_callback` to be invoked during '{ext}' compression."
    )
    assert all(d > 0 and 0.0 <= p <= d + 0.5 for d, p, _, _ in progress_calls), (
        f"[audio] Invalid progress bounds reported during '{ext}' compression: {progress_calls}."
    )


@requires_libvorbis
def test_file_compressor_handles_mono_ogg_at_max_quality_without_vorbis_error(
    sample_audio_factory, tmp_path: Path
):
    """Mono OGG compressed at quality=100 must succeed via the 256 kbps channel-aware cap."""
    src = sample_audio_factory(
        "mono_voice.ogg", duration=1.5, bitrate="192k", channels=1
    )
    dst = tmp_path / "compressed" / "mono_voice.ogg"

    res = audio_file_compression.file_compressor(
        input_path=src,
        output_path=dst,
        quality=100,
    )

    assert res and not res.is_failed, (
        "[audio] Mono OGG compression at quality=100 failed; libvorbis mono cap (256 kbps) should prevent error -22."
    )
    assert dst.exists() and dst.stat().st_size > 0, (
        "[audio] Output file for mono OGG compression is missing or empty."
    )


@pytest.mark.parametrize("ext", ["wav", "flac", "aiff"])
def test_file_compressor_copies_uncompressible_formats_atomically(
    sample_audio_factory, tmp_path: Path, ext: str, monkeypatch
):
    """Formats in `UNCOMPRESSIBLE_AUDIO_FORMATS` must be copied untouched and marked skipped without calling FFmpeg."""
    src = sample_audio_factory(f"lossless.{ext}", duration=0.8)
    dst = tmp_path / "compressed" / f"lossless.{ext}"

    def _forbid_strategies(*args, **kwargs):
        raise AssertionError(
            f"run_audio_strategies must NOT be called for uncompressible format '{ext.upper()}'."
        )

    monkeypatch.setattr(
        audio_file_compression, "run_audio_strategies", _forbid_strategies
    )

    res = audio_file_compression.file_compressor(
        input_path=src,
        output_path=dst,
        quality=50,
    )

    assert res and res.is_skipped and res.reason_key == "skip_audio_not_reencoded", (
        f"[audio] Uncompressible format '{ext}' should return skipped ('skip_audio_not_reencoded'), got {res}."
    )
    assert dst.read_bytes() == src.read_bytes(), (
        f"[audio] Uncompressible format '{ext}' must preserve exact source bytes."
    )


def test_file_compressor_copies_wma_uncompressible_format_atomically(
    tmp_path: Path, monkeypatch
):
    """`WMA` in `UNCOMPRESSIBLE_AUDIO_FORMATS` must bypass FFmpeg transcoding, copy atomically, and return skipped."""
    src = tmp_path / "legacy_track.wma"
    payload = b"ASF_WMA_HEADER_AND_AUDIO_PAYLOAD_BYTES"
    src.write_bytes(payload)
    dst = tmp_path / "compressed" / "legacy_track.wma"

    monkeypatch.setattr(
        audio_file_compression,
        "probe_audio_streams",
        lambda *_args, **_kwargs: audio_ffmpeg_utils.AudioStreamInfo(
            duration_seconds=12.0,
            audio_codecs=["wmav2"],
            sample_rate=44100,
            channels=2,
            channel_layout="stereo",
        ),
    )

    def _forbid_strategies(*args, **kwargs):
        raise AssertionError(
            "run_audio_strategies must NOT be called for uncompressible format 'WMA'."
        )

    monkeypatch.setattr(
        audio_file_compression, "run_audio_strategies", _forbid_strategies
    )

    res = audio_file_compression.file_compressor(
        input_path=src,
        output_path=dst,
        quality=50,
    )

    assert res and res.is_skipped and res.reason_key == "skip_audio_not_reencoded", (
        f"[audio] Uncompressible format 'wma' should return skipped ('skip_audio_not_reencoded'), got {res}."
    )
    assert dst.exists() and dst.read_bytes() == payload, (
        "[audio] Uncompressible format 'wma' must preserve exact source bytes."
    )


@requires_libmp3lame
def test_file_compressor_keeps_original_when_compressed_is_not_smaller(
    sample_audio_factory, tmp_path: Path
):
    """If re-encoding at high quality produces a larger file, the original file must be preserved and marked skipped."""
    src = sample_audio_factory("already_tiny.mp3", duration=1.5, bitrate="48k")
    dst = tmp_path / "compressed" / "already_tiny.mp3"

    res = audio_file_compression.file_compressor(
        input_path=src,
        output_path=dst,
        quality=100,
    )

    assert res and res.is_skipped and res.reason_key == "skip_not_smaller", (
        f"[audio] Compression fallback to original file must return skipped ('skip_not_smaller'), got {res}."
    )
    assert dst.read_bytes() == src.read_bytes(), (
        "[audio] When compressed output >= original size, destination must match original bytes exactly."
    )


@requires_libmp3lame
def test_file_compressor_rejects_invalid_and_handles_cancellation(
    sample_audio_factory, tmp_path: Path
):
    """`file_compressor` must validate paths/streams and clean up temp files on cancellation."""
    valid = sample_audio_factory("source.mp3", duration=1.0, bitrate="192k")

    same_res = audio_file_compression.file_compressor(valid, valid, quality=50)
    assert same_res.is_failed and not same_res, (
        "[audio] Compressor must refuse overwriting source file when input_path == output_path."
    )

    missing_res = audio_file_compression.file_compressor(
        tmp_path / "ghost.mp3", tmp_path / "out.mp3", quality=50
    )
    assert missing_res.is_failed and not missing_res, (
        "[audio] Compressor must return failed FileResult for missing input file."
    )

    cancel = threading.Event()
    cancel.set()
    out_dir = tmp_path / "cancel_out"
    with pytest.raises(InterruptedError):
        audio_file_compression.file_compressor(
            input_path=valid,
            output_path=out_dir / "source.mp3",
            quality=50,
            cancel_event=cancel,
        )

    leftover_tmps = list(out_dir.glob(".*_tmp_*")) if out_dir.exists() else []
    assert not leftover_tmps, (
        f"[audio] Cancelled compression left temporary files behind: {leftover_tmps}."
    )


@pytest.mark.parametrize("ext", ["mp3", "m4a", "opus"])
def test_file_compressor_monotonic_size_across_quality_curve(
    sample_audio_factory, tmp_path: Path, ext: str
):
    """Higher quality values (20 < 60 < 95) must produce strictly larger files on lossy encoders."""
    skip_if_format_encoders_unavailable(ext)
    src = sample_audio_factory(f"master_{ext}.wav", duration=2.5, channels=2)
    high_src = tmp_path / f"source_high.{ext}"
    prep_res = audio_file_conversion.file_converter(src, high_src, target_format=ext)
    assert prep_res.is_processed, (
        f"[audio] Failed to prepare baseline '{ext}' file for quality curve test: {prep_res}."
    )

    sizes: dict[int, int] = {}
    for q in (20, 60, 95):
        out = tmp_path / f"out_q{q}.{ext}"
        res = audio_file_compression.file_compressor(
            input_path=high_src,
            output_path=out,
            quality=q,
        )
        assert res, f"[audio] Compression failed for '{ext}' at quality={q}: {res}."
        sizes[q] = out.stat().st_size

    assert sizes[20] < sizes[60] <= sizes[95], (
        f"[audio] Expected compressed file sizes for '{ext}' to grow with quality "
        f"(q20 < q60 <= q95), got {sizes}."
    )
