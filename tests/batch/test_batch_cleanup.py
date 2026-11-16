"""Tests for batch cancellation rollback and safe session file cleanup."""

import threading

from src.audio import audio_directory_conversion as audio_conversion
from src.image import image_directory_compression as image_compression
from src.utils.batch_runner import run_batch
from src.utils.cleanup import safe_cleanup_session_files
from src.video import video_directory_compression as video_compression
from src.video import video_directory_conversion as video_conversion


def test_image_batch_cancellation_removes_empty_session_folder(
    tmp_workspace, monkeypatch
):
    """Ensures image batch cancellation removes leftover empty session folder."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "photo.png").write_bytes(b"image data")

    cancel_event = threading.Event()
    cancel_event.set()

    stats = image_compression.directory_compressor(
        in_dir, out_dir, quality=80, cancel_event=cancel_event
    )

    assert stats["cancelled"] is True, (
        "[batch] Pre-set cancel_event must mark image batch stats as cancelled=True."
    )
    assert list(out_dir.iterdir()) == [], (
        "[batch] Cancelled image batch must remove its empty session folder from output_dir."
    )


def test_video_batch_conversion_cleans_up_when_cancelled(
    tmp_workspace, monkeypatch
):
    """Ensures an interruption inside the file processor triggers session cleanup."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "a_clip.avi").write_bytes(b"first source")
    (in_dir / "b_clip.mov").write_bytes(b"second source")

    def fake_converter(
        input_path, output_path, target_format, cancel_event=None, **_kwargs
    ):
        if input_path.name == "b_clip.mov":
            raise InterruptedError("CANCELLED_BY_USER")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(input_path.read_bytes())
        return True

    monkeypatch.setattr(
        video_conversion, "file_converter", fake_converter
    )

    stats = video_conversion.directory_converter(
        in_dir, out_dir, target_format="mp4", cancel_event=threading.Event()
    )

    assert stats["cancelled"] is True, (
        "[batch] InterruptedError during video batch conversion must set cancelled=True."
    )
    assert stats["cleaned_files_count"] == 1, (
        "[batch] Mid-batch cancellation must delete the 1 file created earlier in the same session."
    )
    assert not (out_dir / "converted").exists(), (
        "[batch] Empty 'converted' session directory must be removed after all session files are cleaned."
    )


def test_video_batch_compression_removes_empty_session_folder_when_cancelled(
    tmp_workspace, monkeypatch
):
    """Ensures cancelling a compression batch leaves no empty session folder behind."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "clip.mp4").write_bytes(b"source")

    def fake_compressor(
        input_path, output_path, quality, cancel_event=None, **_kwargs
    ):
        raise InterruptedError("CANCELLED_BY_USER")

    monkeypatch.setattr(
        video_compression, "file_compressor", fake_compressor
    )

    stats = video_compression.directory_compressor(
        in_dir, out_dir, quality=80, cancel_event=threading.Event()
    )

    assert stats["cancelled"] is True, (
        "[batch] InterruptedError during video batch compression must set cancelled=True."
    )
    assert list(out_dir.iterdir()) == [], (
        "[batch] Cancelling video compression on the first file must leave no empty session directory behind."
    )


def test_audio_batch_conversion_cleans_up_when_cancelled(
    tmp_workspace, monkeypatch
):
    """Ensures an interruption inside the audio file processor triggers session cleanup."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "a_track.wav").write_bytes(b"first source")
    (in_dir / "b_track.flac").write_bytes(b"second source")

    def fake_converter(
        input_path, output_path, target_format, cancel_event=None, **_kwargs
    ):
        if input_path.name == "b_track.flac":
            raise InterruptedError("CANCELLED_BY_USER")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(input_path.read_bytes())
        return True

    monkeypatch.setattr(
        audio_conversion, "file_converter", fake_converter
    )

    stats = audio_conversion.directory_converter(
        in_dir, out_dir, target_format="mp3", cancel_event=threading.Event()
    )

    assert stats["cancelled"] is True, (
        "[batch] InterruptedError during audio batch conversion must set cancelled=True."
    )
    assert stats["cleaned_files_count"] == 1, (
        "[batch] Mid-batch audio cancellation must clean up the previously created session file."
    )
    assert not (out_dir / "converted").exists(), (
        "[batch] Empty audio 'converted' session directory must be removed after cleanup."
    )


def test_safe_cleanup_preserves_user_files(tmp_workspace):
    """Verifies that session cleanup removes temporary files without touching user files."""
    _, out_dir = tmp_workspace

    user_file = out_dir / "important_user_doc.txt"
    user_file.write_text("user data")

    session_file = out_dir / "subfolder" / "temp_output.png"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text("temporary image data")

    cleaned_count = safe_cleanup_session_files(
        [session_file], root_output_dir=out_dir
    )

    assert cleaned_count == 1, (
        "[batch] safe_cleanup_session_files must report 1 removed session file."
    )
    assert not session_file.exists(), (
        "[batch] Tracked session output file must be deleted during cleanup."
    )
    assert user_file.exists(), (
        "[batch] Untracked user files in root_output_dir must never be deleted during cleanup."
    )
    assert user_file.read_text() == "user data", (
        "[batch] Untracked user file contents must remain completely unmodified."
    )


def test_safe_cleanup_preserves_pre_existing_files(tmp_workspace):
    """Verifies that safe_cleanup_session_files does not delete pre-existing files."""
    _, out_dir = tmp_workspace

    existing_file = out_dir / "pre_existing_output.mp4"
    existing_file.write_text("original user data")

    cleaned_count = safe_cleanup_session_files(
        created_files=[existing_file],
        root_output_dir=out_dir,
        pre_existing_files=[existing_file],
    )

    assert cleaned_count == 0, (
        "[batch] Files listed in pre_existing_files must not be counted or removed as session artifacts."
    )
    assert existing_file.exists(), (
        "[batch] Pre-existing file must remain on disk after safe_cleanup_session_files."
    )
    assert existing_file.read_text() == "original user data", (
        "[batch] Pre-existing file contents must remain intact after cleanup."
    )


def test_run_batch_cleans_up_without_deleting_pre_existing_files(tmp_workspace):
    """Ensures batch cancellation preserves pre-existing files that were overwritten."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "file1.png").write_bytes(b"source 1")
    (in_dir / "file2.png").write_bytes(b"source 2")

    session_dir = out_dir / "compressed"
    session_dir.mkdir(parents=True, exist_ok=True)

    pre_existing_file = session_dir / "file1.png"
    pre_existing_file.write_bytes(b"pre-existing data")

    def process_with_cancel(src_file, dst_file):
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        dst_file.write_bytes(b"new data")
        if src_file.name == "file2.png":
            raise InterruptedError("CANCELLED")
        return True

    stats = run_batch(
        input_dir=in_dir,
        output_dir=out_dir,
        session_name="compressed",
        scanner=lambda p: sorted(p.glob("*.png")),
        process_file=process_with_cancel,
        build_destination=lambda src, s_dir: session_dir / src.name,
    )

    assert stats["cancelled"] is True, (
        "[batch] Batch cancellation must set cancelled=True in returned stats."
    )
    assert pre_existing_file.exists(), (
        "[batch] Pre-existing file path in session directory must not be unlinked during cancellation cleanup."
    )
    assert pre_existing_file.read_bytes() == b"new data", (
        "[batch] Pre-existing file retained on disk should reflect the completed first-item write."
    )