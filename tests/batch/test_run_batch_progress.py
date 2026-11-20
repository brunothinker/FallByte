"""Batch runner progress reporting and callback error handling."""

from pathlib import Path

from src.utils.batch_runner import run_batch
from src.utils.progress import ProgressInfo


def test_run_batch_reports_total_files(tmp_path):
    """run_batch must report the number of scanned files, failed ones included.

    Controllers build their summary message ("X of Y") from `total_files`, and
    the controller tests use fake engines that always provide it, so this is
    the only test guarding the real `run_batch` output.
    """
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    for name in ("a.png", "b.png", "c.png"):
        (input_dir / name).write_bytes(b"x")

    def process(src_file, dst_file):
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        dst_file.write_bytes(b"x")
        return src_file.name != "c.png"  # c.png is reported as a failure

    stats = run_batch(
        input_dir=input_dir,
        output_dir=tmp_path / "out",
        session_name="compressed",
        scanner=lambda path: sorted(path.glob("*.png")),
        process_file=process,
        build_destination=lambda src_file, session_dir: session_dir / src_file.name,
    )

    assert stats["total_files"] == 3, (
        "[batch] run_batch must report the total count of scanned files including failed items."
    )
    assert stats["success"] == 2, (
        "[batch] run_batch must count files where process_file returned True as successes."
    )
    assert stats["failed"] == 1, (
        "[batch] run_batch must count files where process_file returned False as failures."
    )
    assert stats["success"] + stats["failed"] == stats["total_files"], (
        "[batch] Batch invariant violated: success + failed must equal total_files."
    )
    assert "no_files" not in stats, (
        "[batch] Non-empty batch runs must not set the 'no_files' flag."
    )


def test_run_batch_reports_zero_total_files_when_nothing_to_process(tmp_path):
    """An empty scan reports total_files == 0 together with the no_files flag."""
    stats = run_batch(
        input_dir=tmp_path,
        output_dir=tmp_path / "out",
        session_name="compressed",
        scanner=lambda path: [],
        process_file=lambda src_file, dst_file: True,
        build_destination=lambda src_file, session_dir: session_dir / src_file.name,
    )

    assert stats["total_files"] == 0, "[batch] Empty scan must report total_files == 0."
    assert stats["no_files"] is True, (
        "[batch] Empty scan must set no_files=True so callers can surface an empty-folder notice."
    )
    assert not (tmp_path / "out").exists(), (
        "[batch] Empty scan must not create the output directory when there is nothing to process."
    )


def test_run_batch_start_callback_error_is_a_batch_error_not_a_file_failure(tmp_path):
    """An error in the start-of-file progress callback aborts the batch with an explicit error."""
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    for filename in ("a.png", "b.png", "c.png"):
        (input_dir / filename).write_bytes(b"data")

    processed: list[str] = []

    def on_progress(info):
        if not info.is_completed:
            raise RuntimeError("Progress UI crashed")

    def process(src_file, dst_file):
        processed.append(src_file.name)
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        dst_file.write_bytes(b"x")
        return True

    stats = run_batch(
        input_dir=input_dir,
        output_dir=tmp_path / "out",
        session_name="compressed",
        scanner=lambda path: sorted(path.glob("*.png")),
        process_file=process,
        build_destination=lambda src_file, session_dir: session_dir / src_file.name,
        progress_callback=on_progress,
    )

    assert stats.get("error") == "Progress UI crashed", (
        "[batch] A start-callback exception must be returned as stats['error'] with its message."
    )
    assert processed == [], (
        "[batch] Processing must stop when the start callback fails, before any file is processed."
    )
    assert stats["failed"] == 0, (
        "[batch] A callback error must not be counted as a file failure."
    )
    assert stats["success"] == 0, (
        "[batch] No file was processed, so none may be counted as a success."
    )
    assert stats["total_files"] == 3, (
        "[batch] total_files must still reflect the scanned inputs."
    )
    assert stats["cancelled"] is False, (
        "[batch] A callback error must not be misclassified as user cancellation."
    )


def test_run_batch_completion_callback_error_does_not_recount_the_file(tmp_path):
    """An error in the completion callback aborts the batch without turning a success into a failure."""
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    for filename in ("a.png", "b.png", "c.png"):
        (input_dir / filename).write_bytes(b"data")

    processed: list[str] = []

    def on_progress(info):
        if info.is_completed:
            raise RuntimeError("Completion UI crashed")

    def process(src_file, dst_file):
        processed.append(src_file.name)
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        dst_file.write_bytes(b"x")
        return True

    stats = run_batch(
        input_dir=input_dir,
        output_dir=tmp_path / "out",
        session_name="compressed",
        scanner=lambda path: sorted(path.glob("*.png")),
        process_file=process,
        build_destination=lambda src_file, session_dir: session_dir / src_file.name,
        progress_callback=on_progress,
    )

    assert stats.get("error") == "Completion UI crashed", (
        "[batch] A completion-callback exception must be returned as stats['error'] with its message."
    )
    assert processed == ["a.png"], (
        "[batch] Processing must stop after the file whose completion callback failed."
    )
    assert stats["success"] == 1, (
        "[batch] The successfully processed file must be counted exactly once as a success."
    )
    assert stats["failed"] == 0, (
        "[batch] A completion-callback error must not turn a successful file into a failure."
    )
    assert stats["cancelled"] is False, (
        "[batch] A callback error must not be misclassified as user cancellation."
    )


def test_run_batch_video_live_progress_with_fake_processor(tmp_workspace):
    """Verifies live progress updates starting from the first file and off-by-one progress bar calculations."""
    in_dir, out_dir = tmp_workspace
    file1 = in_dir / "clip1.mp4"
    file2 = in_dir / "clip2.mp4"
    file1.write_bytes(b"video data 1")
    file2.write_bytes(b"video data 2")

    captured_updates: list[tuple[int, str, float, bool]] = []
    active_info: ProgressInfo | None = None

    def fake_video_process(src: Path, dst: Path) -> bool:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())

        # Simulate FFmpeg intra-file progress updates
        if active_info:
            active_info.duration_seconds = 10.0
            active_info.processed_seconds = 5.0
            captured_updates.append(
                (
                    active_info.current,
                    active_info.file_path.name if active_info.file_path else "",
                    active_info.percentage,
                    active_info.is_completed,
                )
            )

        return True

    def on_progress(info: ProgressInfo) -> None:
        nonlocal active_info
        active_info = info
        captured_updates.append(
            (
                info.current,
                info.file_path.name if info.file_path else "",
                info.percentage,
                info.is_completed,
            )
        )

    stats = run_batch(
        input_dir=in_dir,
        output_dir=out_dir,
        session_name="compressed",
        scanner=lambda p: sorted(p.glob("*.mp4")),
        process_file=fake_video_process,
        build_destination=lambda src, s_dir: s_dir / src.name,
        progress_callback=on_progress,
    )

    assert stats["total_files"] == 2, (
        "[batch] Expected total_files == 2 for two input clips."
    )
    assert stats["success"] == 2, (
        "[batch] Expected both clips to complete successfully."
    )

    # Validate live progress on the first file
    first_start = captured_updates[0]
    assert first_start == (1, "clip1.mp4", 0.0, False), (
        f"[batch] Initial progress tick for file 1 should start at 0.0%, got {first_start}."
    )

    first_intra = captured_updates[1]
    assert first_intra == (1, "clip1.mp4", 25.0, False), (
        f"[batch] Intra-file 50% progress on file 1 of 2 should compute overall 25.0%, got {first_intra}."
    )

    first_end = captured_updates[2]
    assert first_end == (1, "clip1.mp4", 50.0, True), (
        f"[batch] Completion tick for file 1 of 2 should compute overall 50.0%, got {first_end}."
    )

    # Validate second file progress and 100% completion
    second_end = captured_updates[-1]
    assert second_end == (2, "clip2.mp4", 100.0, True), (
        f"[batch] Final completion tick for file 2 of 2 must reach 100.0%, got {second_end}."
    )
