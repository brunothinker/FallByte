"""Tests for the generic `run_batch` statistics contract and live progress reporting."""

import logging
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


def test_run_batch_handles_unexpected_exception(tmp_path, caplog):
    """Ensures run_batch handles unexpected inner exceptions cleanly without session cleanup."""
    input_dir = tmp_path / "in"
    input_dir.mkdir()

    for filename in ("a.png", "b.png", "c.png"):
        (input_dir / filename).write_bytes(b"data")

    def process_with_error(src_file, dst_file):
        if src_file.name == "b.png":
            raise RuntimeError("Unexpected engine crash")
        return True

    with caplog.at_level(logging.ERROR, logger="src.utils.batch_runner"):
        stats = run_batch(
            input_dir=input_dir,
            output_dir=tmp_path / "out",
            session_name="compressed",
            scanner=lambda path: sorted(path.glob("*.png")),
            process_file=process_with_error,
            build_destination=lambda src_file, session_dir: session_dir / src_file.name,
        )

    assert stats["cancelled"] is False, (
        "[batch] Unexpected engine exceptions must not be misclassified as user cancellation."
    )
    error_messages = [
        record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.ERROR
    ]
    assert any(str(input_dir / "b.png") in message for message in error_messages), (
        "[batch] The error log must include the path of the second file whose processor crashed."
    )
    assert stats["total_files"] == 3, (
        "[batch] total_files must still reflect scanned inputs when an unexpected exception occurs."
    )
    assert stats["success"] == 2, (
        "[batch] Successful file processing must be counted as a success."
    )
    assert stats["failed"] == 1, (
        "[batch] Crashed file processing must be counted as a failure."
    )


def test_run_batch_continues_when_build_destination_fails_for_one_file(tmp_path):
    """A destination-building error on one file is that file's failure, not the batch's."""
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    for filename in ("a.png", "b.png", "c.png"):
        (input_dir / filename).write_bytes(b"data")

    processed: list[str] = []
    progress_updates: list[ProgressInfo] = []

    def build_destination(src_file, session_dir):
        if src_file.name == "b.png":
            raise ValueError("Cannot build destination")
        return session_dir / src_file.name

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
        build_destination=build_destination,
        progress_callback=progress_updates.append,
    )

    assert processed == ["a.png", "c.png"], (
        "[batch] The processor must receive the first and third files and never the file whose destination failed."
    )
    assert stats["total_files"] == 3, (
        "[batch] total_files must still count the file whose destination could not be built."
    )
    assert stats["success"] == 2, (
        "[batch] Files processed after a destination failure must still be counted as successes."
    )
    assert stats["failed"] == 1, (
        "[batch] A destination-building failure must be counted as exactly one failed file."
    )
    assert stats["cancelled"] is False, (
        "[batch] A destination-building failure must not be misclassified as user cancellation."
    )

    failed_file_updates = [
        info
        for info in progress_updates
        if info.file_path is not None and info.file_path.name == "b.png"
    ]
    completed_failed_updates = [
        info for info in failed_file_updates if info.is_completed and not info.success
    ]
    assert len(completed_failed_updates) == 1, (
        "[batch] The failed file must get exactly one completed, unsuccessful progress update."
    )
    assert not any(info.success for info in failed_file_updates), (
        "[batch] The failed file must never be reported as successful in progress updates."
    )


def test_run_batch_cancellation_cleans_up_output_and_is_not_a_failure(tmp_path):
    """InterruptedError mid-batch cancels the run, removes new outputs and counts no failure."""
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    for filename in ("a.png", "b.png", "c.png"):
        (input_dir / filename).write_bytes(b"data")

    processed: list[str] = []
    first_output: dict[str, Path] = {}
    first_output_existed_at_cancel: list[bool] = []

    def process(src_file, dst_file):
        processed.append(src_file.name)
        if src_file.name == "b.png":
            first_output_existed_at_cancel.append(first_output["a.png"].exists())
            raise InterruptedError("Cancelled while processing")
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        dst_file.write_bytes(b"x")
        first_output[src_file.name] = dst_file
        return True

    stats = run_batch(
        input_dir=input_dir,
        output_dir=tmp_path / "out",
        session_name="compressed",
        scanner=lambda path: sorted(path.glob("*.png")),
        process_file=process,
        build_destination=lambda src_file, session_dir: session_dir / src_file.name,
    )

    assert processed == ["a.png", "b.png"], (
        "[batch] After cancellation the third file must never be handed to the processor."
    )
    assert stats["cancelled"] is True, (
        "[batch] InterruptedError from the processor must mark the batch as cancelled."
    )
    assert stats["failed"] == 0, (
        "[batch] Cancellation must not be counted as a failed file."
    )
    assert first_output_existed_at_cancel == [True], (
        "[batch] Precondition: the first file's output must exist when cancellation happens."
    )
    assert not first_output["a.png"].exists(), (
        "[batch] The first file's newly created output must be removed by cancellation cleanup."
    )
    assert stats["cleaned_files_count"] == 1, (
        "[batch] Cancellation cleanup must report exactly the one output file it removed."
    )


def test_run_batch_cancellation_after_file_error_cleans_up_both_outputs(tmp_path):
    """After one file error, a later cancellation removes both new outputs and counts one failure."""
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    for filename in ("a.png", "b.png", "c.png"):
        (input_dir / filename).write_bytes(b"data")

    output_dir = tmp_path / "out"
    assert not output_dir.exists(), (
        "[batch] Precondition: no destination files may exist before the batch starts."
    )

    destinations: dict[str, Path] = {}

    def process(src_file, dst_file):
        if src_file.name == "c.png":
            raise InterruptedError("Cancelled while processing")
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        dst_file.write_bytes(b"x")
        destinations[src_file.name] = dst_file
        if src_file.name == "b.png":
            raise RuntimeError("Engine crash after writing output")
        return True

    stats = run_batch(
        input_dir=input_dir,
        output_dir=output_dir,
        session_name="compressed",
        scanner=lambda path: sorted(path.glob("*.png")),
        process_file=process,
        build_destination=lambda src_file, session_dir: session_dir / src_file.name,
    )

    assert stats["cancelled"] is True, (
        "[batch] InterruptedError on the third file must mark the batch as cancelled."
    )
    assert stats["failed"] == 1, (
        "[batch] Only the ordinary RuntimeError must be counted as a failure; cancellation must not add one."
    )
    assert stats["success"] == 1, (
        "[batch] Only the first file completed successfully before cancellation."
    )
    assert not destinations["a.png"].exists(), (
        "[batch] Cancellation cleanup must remove the first file's new output."
    )
    assert not destinations["b.png"].exists(), (
        "[batch] Cancellation cleanup must remove the failed file's new output."
    )
    assert stats["cleaned_files_count"] == 2, (
        "[batch] Cancellation cleanup must report both newly created outputs as removed."
    )


def test_run_batch_cancellation_preserves_pre_existing_destination_after_file_error(
    tmp_path,
):
    """A pre-existing destination that fails mid-batch must survive a later cancellation."""
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    for filename in ("a.png", "b.png", "c.png"):
        (input_dir / filename).write_bytes(b"data")

    # b.png's destination already exists before the batch starts.
    existing_dir = tmp_path / "existing"
    existing_dir.mkdir()
    existing_destination = existing_dir / "b.png"
    existing_destination.write_bytes(b"original")

    destinations: dict[str, Path] = {}

    def build_destination(src_file, session_dir):
        if src_file.name == "b.png":
            return existing_destination
        return session_dir / src_file.name

    def process(src_file, dst_file):
        if src_file.name == "c.png":
            raise InterruptedError("Cancelled while processing")
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        dst_file.write_bytes(b"x")
        destinations[src_file.name] = dst_file
        if src_file.name == "b.png":
            raise RuntimeError("Engine crash after writing output")
        return True

    stats = run_batch(
        input_dir=input_dir,
        output_dir=tmp_path / "out",
        session_name="compressed",
        scanner=lambda path: sorted(path.glob("*.png")),
        process_file=process,
        build_destination=build_destination,
    )

    assert stats["cancelled"] is True, (
        "[batch] InterruptedError on the third file must mark the batch as cancelled."
    )
    assert stats["failed"] == 1, (
        "[batch] Only the ordinary RuntimeError must be counted as a failure."
    )
    assert not destinations["a.png"].exists(), (
        "[batch] Cancellation cleanup must remove the first file's new output."
    )
    assert existing_destination.exists(), (
        "[batch] A destination that existed before processing must never be deleted by cleanup."
    )
    assert stats["cleaned_files_count"] == 1, (
        "[batch] Cleanup must remove only the one newly created output, not the pre-existing file."
    )


def test_run_batch_cancellation_removes_output_of_interrupted_file(tmp_path):
    """A file that writes a new output and is then interrupted must have it cleaned up."""
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    for filename in ("a.png", "b.png", "c.png"):
        (input_dir / filename).write_bytes(b"data")

    processed: list[str] = []
    destinations: dict[str, Path] = {}

    def process(src_file, dst_file):
        processed.append(src_file.name)
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        dst_file.write_bytes(b"partial")
        destinations[src_file.name] = dst_file
        raise InterruptedError("Cancelled while processing")

    stats = run_batch(
        input_dir=input_dir,
        output_dir=tmp_path / "out",
        session_name="compressed",
        scanner=lambda path: sorted(path.glob("*.png")),
        process_file=process,
        build_destination=lambda src_file, session_dir: session_dir / src_file.name,
    )

    assert processed == ["a.png"], (
        "[batch] Cancellation must stop further processing after the interrupted file."
    )
    assert stats["cancelled"] is True, (
        "[batch] InterruptedError from the processor must mark the batch as cancelled."
    )
    assert stats["failed"] == 0, (
        "[batch] Cancellation must not be counted as a failed file."
    )
    assert not destinations["a.png"].exists(), (
        "[batch] The interrupted file's newly created output must be removed by cleanup."
    )
    assert stats["cleaned_files_count"] == 1, (
        "[batch] Cleanup must report the one output created by the interrupted file."
    )


def test_run_batch_tracking_error_does_not_replace_cancellation(tmp_path):
    """A filesystem error while registering the output must not replace the cancellation."""
    # Explicit test state: existence checks behave normally until the processor
    # starts, then raise OSError (as during output tracking after the interruption).
    state = {"fail_exists": False, "errors_raised": 0}

    class FlakyExistsPath(type(Path())):
        """Behaves normally until `state["fail_exists"]` is set, then exists() raises."""

        def exists(self, *args, **kwargs):
            if state["fail_exists"]:
                state["errors_raised"] += 1
                raise OSError("Simulated filesystem failure")
            return super().exists(*args, **kwargs)

    input_dir = tmp_path / "in"
    input_dir.mkdir()
    for filename in ("a.png", "b.png"):
        (input_dir / filename).write_bytes(b"data")

    flaky_destination = FlakyExistsPath(tmp_path / "flaky_a.png")
    processed: list[str] = []

    def process(src_file, dst_file):
        processed.append(src_file.name)
        state["fail_exists"] = True
        Path(dst_file).write_bytes(b"partial")
        raise InterruptedError("Cancelled while processing")

    stats = run_batch(
        input_dir=input_dir,
        output_dir=tmp_path / "out",
        session_name="compressed",
        scanner=lambda path: sorted(path.glob("*.png")),
        process_file=process,
        build_destination=lambda src_file, session_dir: flaky_destination,
    )

    assert state["errors_raised"] >= 1, (
        "[batch] Precondition: output tracking must have hit the simulated filesystem error."
    )
    assert processed == ["a.png"], (
        "[batch] Cancellation must stop further processing even if output tracking fails."
    )
    assert stats["cancelled"] is True, (
        "[batch] A filesystem error while tracking must not replace the cancellation."
    )
    assert stats["failed"] == 0, (
        "[batch] A tracking error during cancellation must not be counted as a failed file."
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


def test_run_batch_scanner_error_returns_batch_error(tmp_path):
    """A scanner failure is returned as a batch-level error and processes nothing."""
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    processed: list[str] = []

    def failing_scanner(path):
        raise OSError("Cannot read input folder")

    def process(src_file, dst_file):
        processed.append(src_file.name)
        return True

    stats = run_batch(
        input_dir=input_dir,
        output_dir=tmp_path / "out",
        session_name="compressed",
        scanner=failing_scanner,
        process_file=process,
        build_destination=lambda src_file, session_dir: session_dir / src_file.name,
    )

    assert stats.get("error") == "Cannot read input folder", (
        "[batch] A scanner failure must be returned as stats['error'] with its message."
    )
    assert processed == [], "[batch] No file may be processed when scanning fails."
    assert stats["cancelled"] is False, (
        "[batch] A scanner failure must not be classified as user cancellation."
    )
    assert stats["failed"] == 0 and stats["success"] == 0, (
        "[batch] A scanner failure must not be counted as an individual file failure."
    )
    assert isinstance(stats["elapsed_seconds"], float), (
        "[batch] The returned stats must keep a numeric elapsed time."
    )
    assert not (tmp_path / "out").exists(), (
        "[batch] No output folder may be created when scanning fails."
    )


def test_run_batch_output_folder_error_returns_batch_error(tmp_path, monkeypatch):
    """A failure creating the session output folder is a batch error and processes nothing."""
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    for filename in ("a.png", "b.png", "c.png"):
        (input_dir / filename).write_bytes(b"data")
    processed: list[str] = []

    def failing_create_dir(output_dir, folder_name):
        raise OSError("Cannot create output folder")

    monkeypatch.setattr(
        "src.utils.batch_runner.create_unique_output_dir", failing_create_dir
    )

    def process(src_file, dst_file):
        processed.append(src_file.name)
        return True

    stats = run_batch(
        input_dir=input_dir,
        output_dir=tmp_path / "out",
        session_name="compressed",
        scanner=lambda path: sorted(path.glob("*.png")),
        process_file=process,
        build_destination=lambda src_file, session_dir: session_dir / src_file.name,
    )

    assert stats.get("error") == "Cannot create output folder", (
        "[batch] An output-folder failure must be returned as stats['error'] with its message."
    )
    assert processed == [], (
        "[batch] No file may be processed when the output folder cannot be created."
    )
    assert stats["total_files"] == 3, (
        "[batch] total_files must still reflect the scanned inputs."
    )
    assert stats["cancelled"] is False, (
        "[batch] An output-folder failure must not be classified as user cancellation."
    )
    assert stats["failed"] == 0 and stats["success"] == 0, (
        "[batch] An output-folder failure must not be counted as an individual file failure."
    )
    assert "no_files" not in stats, (
        "[batch] Non-empty input must not be reported as an empty folder."
    )


def test_run_batch_cancellation_before_session_folder_exists_is_safe(tmp_path):
    """Cancelling during scanning, before any session folder exists, must not need cleanup."""
    input_dir = tmp_path / "in"
    input_dir.mkdir()

    def cancelled_scanner(path):
        raise InterruptedError("Cancelled while scanning")

    stats = run_batch(
        input_dir=input_dir,
        output_dir=tmp_path / "out",
        session_name="compressed",
        scanner=cancelled_scanner,
        process_file=lambda src_file, dst_file: True,
        build_destination=lambda src_file, session_dir: session_dir / src_file.name,
    )

    assert stats["cancelled"] is True, (
        "[batch] InterruptedError during scanning must still be reported as cancellation."
    )
    assert "error" not in stats, (
        "[batch] Cancellation must not be reported as a batch error."
    )
    assert stats["failed"] == 0 and stats["cleaned_files_count"] == 0, (
        "[batch] Cancellation before any output exists must count no failure and clean nothing."
    )
    assert not (tmp_path / "out").exists(), (
        "[batch] No output folder may be created when cancelled during scanning."
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
