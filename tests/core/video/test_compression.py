"""Core (video): testes de compression (engines de arquivo e de diretorio)."""

import threading

import pytest

from src.video import video_directory_compression as video_compression
from src.video.video_file_compression import file_compressor as video_compressor


def test_video_batch_compression_removes_empty_session_folder_when_cancelled(
    tmp_workspace, monkeypatch
):
    """Ensures cancelling a compression batch leaves no empty session folder behind."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "clip.mp4").write_bytes(b"source")

    def fake_compressor(input_path, output_path, quality, cancel_event=None, **_kwargs):
        raise InterruptedError("CANCELLED_BY_USER")

    monkeypatch.setattr(video_compression, "file_compressor", fake_compressor)

    stats = video_compression.directory_compressor(
        in_dir, out_dir, quality=80, cancel_event=threading.Event()
    )

    assert stats["cancelled"] is True, (
        "[batch] InterruptedError during video batch compression must set cancelled=True."
    )
    assert list(out_dir.iterdir()) == [], (
        "[batch] Cancelling video compression on the first file must leave no empty session directory behind."
    )


def test_video_compressor_raises_when_cancelled(tmp_workspace, create_sample_video):
    """Ensures a pre-set cancel event raises InterruptedError and leaves no output."""
    in_dir, out_dir = tmp_workspace
    src_mp4 = create_sample_video(in_dir / "input.mp4", duration_sec=1)
    dst_file = out_dir / "compressed.mp4"

    cancel_event = threading.Event()
    cancel_event.set()

    with pytest.raises(InterruptedError):
        video_compressor(src_mp4, dst_file, quality=60, cancel_event=cancel_event)

    assert not dst_file.exists(), (
        "[video] Pre-cancelled video compression must not produce an output file."
    )


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
