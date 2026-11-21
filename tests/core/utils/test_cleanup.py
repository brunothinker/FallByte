"""Core: cleanup seguro de saidas de batch."""

from src.utils.batch_runner import run_batch
from src.utils.cleanup import safe_cleanup_session_files


def test_safe_cleanup_preserves_user_files(tmp_workspace):
    """Verifies that session cleanup removes temporary files without touching user files."""
    _, out_dir = tmp_workspace

    user_file = out_dir / "important_user_doc.txt"
    user_file.write_text("user data")

    session_file = out_dir / "subfolder" / "temp_output.png"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text("temporary image data")

    cleaned_count = safe_cleanup_session_files([session_file], root_output_dir=out_dir)

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
