"""Batch runner cancellation semantics: output cleanup and pre-existing file preservation."""

from pathlib import Path

from src.utils.batch_runner import run_batch


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
