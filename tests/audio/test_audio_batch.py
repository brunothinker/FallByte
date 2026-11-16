"""Tests for audio directory batch conversion and compression orchestrators."""

import threading
from pathlib import Path

from src.audio import audio_directory_compression, audio_directory_conversion
from tests.audio.helpers import requires_libmp3lame, requires_libvorbis


@requires_libmp3lame
@requires_libvorbis
def test_directory_converter_preserves_hierarchy_and_handles_name_collisions(
    sample_audio_factory, tmp_path: Path
):
    """`directory_converter` must preserve folder hierarchy, isolate bad files, and avoid collisions."""
    in_dir = tmp_path / "input"
    out_dir = tmp_path / "output"

    sample_audio_factory("input/song.wav", duration=0.8)
    sample_audio_factory("input/song.flac", duration=0.8)  # same stem -> collision test
    sample_audio_factory("input/album/track01.ogg", duration=0.8)
    (in_dir / "broken.mp3").write_bytes(b"corrupted-audio")

    progress_events = []
    stats = audio_directory_conversion.directory_converter(
        input_dir=in_dir,
        output_dir=out_dir,
        target_format="mp3",
        progress_callback=progress_events.append,
    )

    assert stats["total_files"] == 4, (
        f"[audio] Expected 4 scanned audio files, got {stats['total_files']}."
    )
    assert stats["success"] == 3, (
        f"[audio] Expected 3 successful conversions, got {stats['success']} (stats={stats})."
    )
    assert stats["failed"] == 1, (
        f"[audio] Expected 1 failed conversion for corrupted file, got {stats['failed']}."
    )

    session_dir = out_dir / "converted"
    converted_mp3s = sorted(session_dir.rglob("*.mp3"))
    assert len(converted_mp3s) == 3, (
        f"[audio] Expected 3 unique converted MP3 files in '{session_dir}', got {converted_mp3s}."
    )
    assert (session_dir / "album" / "track01_converted.mp3").exists(), (
        "[audio] Subdirectory structure 'album/' was not preserved during batch conversion."
    )
    assert any(p.is_completed for p in progress_events), (
        "[audio] Expected `progress_callback` to emit completed ProgressInfo events."
    )


@requires_libmp3lame
def test_directory_compressor_preserves_hierarchy_and_formats(
    sample_audio_factory, tmp_path: Path
):
    """`directory_compressor` must compress lossy files, copy lossless ones, and keep folder structure."""
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
        stats["total_files"] == 2 and stats["success"] == 2 and stats["failed"] == 0
    ), f"[audio] Expected 2/2 successful batch compressions, got stats={stats}."

    session_dir = out_dir / "compressed"
    dst_mp3 = session_dir / "podcast.mp3"
    dst_wav = session_dir / "sub" / "master.wav"

    assert dst_mp3.exists() and dst_mp3.stat().st_size < src_mp3.stat().st_size, (
        "[audio] Batch compressor did not reduce size of high-bitrate MP3 file."
    )
    assert dst_wav.exists() and dst_wav.read_bytes() == src_wav.read_bytes(), (
        "[audio] Batch compressor did not preserve untouched bytes for lossless WAV file."
    )


def test_directory_operations_handle_empty_dir_and_cancellation(
    sample_audio_factory, tmp_path: Path
):
    """Empty directories must return `no_files=True`, and cancellation must clean up session files."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    out_dir = tmp_path / "out"

    empty_stats = audio_directory_conversion.directory_converter(
        input_dir=empty_dir,
        output_dir=out_dir,
        target_format="mp3",
    )
    assert empty_stats.get("no_files") is True and empty_stats["total_files"] == 0, (
        f"[audio] Expected `no_files=True` for empty directory, got {empty_stats}."
    )

    in_dir = tmp_path / "batch_cancel"
    sample_audio_factory("batch_cancel/a.wav", duration=0.8)
    sample_audio_factory("batch_cancel/b.wav", duration=0.8)

    cancel = threading.Event()

    def _cancel_after_first(info):
        if info.is_completed and info.current == 1:
            cancel.set()

    cancel_stats = audio_directory_compression.directory_compressor(
        input_dir=in_dir,
        output_dir=out_dir,
        quality=50,
        progress_callback=_cancel_after_first,
        cancel_event=cancel,
    )

    assert cancel_stats["cancelled"] is True, (
        f"[audio] Expected `cancelled=True` when cancel_event triggered mid-batch, got {cancel_stats}."
    )
    assert cancel_stats["cleaned_files_count"] == 1, (
        f"[audio] Expected 1 previously created session file to be cleaned up, got {cancel_stats}."
    )
    assert not (out_dir / "compressed").exists(), (
        "[audio] Expected empty session directory 'compressed' to be removed after cancellation cleanup."
    )
