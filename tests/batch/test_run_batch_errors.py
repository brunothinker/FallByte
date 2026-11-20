"""Batch runner error handling: per-file failures, scanner and output-folder errors."""

import logging

from src.utils.batch_runner import run_batch
from src.utils.progress import ProgressInfo


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
