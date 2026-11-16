"""Tests for single-file video compression (`src/video/video_file_compression.py`)."""

import pytest

from src.video.video_file_compression import file_compressor as video_compressor


@pytest.mark.parametrize("quality", [30, 60, 80])
def test_video_compression_levels(tmp_workspace, create_sample_video, quality):
    """Tests video compression across multiple quality levels."""
    in_dir, out_dir = tmp_workspace
    src_mp4 = create_sample_video(in_dir / "input.mp4", duration_sec=1)

    dst_mp4 = out_dir / f"compressed_q{quality}.mp4"
    success = video_compressor(src_mp4, dst_mp4, quality=quality)

    assert success is True, (
        f"[video] Video compression at quality={quality} unexpectedly returned False."
    )
    assert dst_mp4.exists(), (
        f"[video] Compressed video output '{dst_mp4}' was not written to disk."
    )
    assert dst_mp4.stat().st_size > 0, (
        f"[video] Compressed video output '{dst_mp4}' is empty (0 bytes)."
    )


def test_video_compression_atomic_keep_original_on_failure(
    tmp_workspace, create_sample_video, monkeypatch
):
    """Ensures failure during 'keep_original' copy leaves destination uncorrupted and no tmp files."""
    in_dir, out_dir = tmp_workspace
    src_mp4 = create_sample_video(in_dir / "input.mp4", duration_sec=1)
    dst_mp4 = out_dir / "input_compressed.mp4"
    dst_mp4.write_bytes(b"original destination data")

    # Force shutil.copy2 to fail during the fallback copy
    def failing_copy2(*args, **kwargs):
        raise OSError("Simulated disk error during copy")

    monkeypatch.setattr("src.utils.cleanup.shutil.copy2", failing_copy2)

    # Compress at quality=100 where compressed output is >= original
    success = video_compressor(src_mp4, dst_mp4, quality=100)

    assert success is False, (
        "[video] Simulated I/O error during keep-original fallback copy must return False."
    )
    assert dst_mp4.exists(), (
        "[video] Failed keep-original fallback copy must not delete pre-existing destination file."
    )
    assert dst_mp4.read_bytes() == b"original destination data", (
        "[video] Failed keep-original fallback copy must preserve pre-existing destination bytes."
    )
    assert list(out_dir.glob(".*_tmp_*")) == [], (
        "[video] Failed keep-original fallback copy leaked temporary files in the output directory."
    )