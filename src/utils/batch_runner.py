import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.utils.cleanup import safe_cleanup_session_files
from src.utils.output_directory import create_unique_output_dir
from src.utils.progress import ProgressInfo

# Setup module logger
logger = logging.getLogger(__name__)


def _track_new_output(dst_file: Path, created_files: list[Path]) -> None:
    """Registers an existing, newly created output for cancellation cleanup.

    Never raises for filesystem errors, so bookkeeping cannot abort the batch or
    turn an ordinary file failure into a batch-level failure. It never deletes anything.
    """
    try:
        if dst_file.exists() and dst_file not in created_files:
            created_files.append(dst_file)
    except OSError:
        logger.warning(f"Could not register output for cleanup: '{dst_file}'")


class _ProgressCallbackError(Exception):
    """Wraps an ordinary progress-callback failure.

    The per-file handler lets this type through so it reaches the batch-level
    handler instead of being counted as a failure of the file being processed.
    """

    def __init__(self, original: Exception) -> None:
        super().__init__(str(original))
        self.original = original


def _emit_progress(
    callback: Callable[[ProgressInfo], None], info: ProgressInfo
) -> None:
    """Calls the progress callback; ordinary errors become `_ProgressCallbackError`.

    `InterruptedError` is passed through untouched so cancellation keeps working.
    """
    try:
        callback(info)
    except InterruptedError:
        raise
    except Exception as exc:
        raise _ProgressCallbackError(exc) from exc


def run_batch(
    input_dir: str | Path,
    output_dir: str | Path,
    session_name: str,
    scanner: Callable[[Path], list[Path]],
    process_file: Callable[[Path, Path], bool],
    build_destination: Callable[[Path, Path], Path],
    progress_callback: Callable[[ProgressInfo], None] | None = None,
    cancel_event: Any | None = None,
    sort: bool = True,
    remove_empty_session_dir: bool = False,
) -> dict[str, Any]:
    """Orchestrates a generic batch processing workflow across multiple media files.

    Handles directory scanning, session folder creation, sequential processing,
    progress tracking metrics, user cancellation signals, and graceful cleanup,
    strictly protecting pre-existing files from corruption or accidental deletion.

    Args:
        input_dir (str | Path): Source directory containing target files.
        output_dir (str | Path): Destination directory for processed results.
        session_name (str): Identifier used to name the unique output subfolder.
        scanner (Callable[[Path], list[Path]]): Function returning a list of valid file paths.
        process_file (Callable[[Path, Path], bool]): Function processing a single file (src -> dst).
        build_destination (Callable[[Path, Path], Path]): Function computing output path for a file.
        progress_callback (Callable[[ProgressInfo], None] | None, optional): Callback receiving
            detailed ProgressInfo instances. Defaults to None.
        cancel_event (Any | None, optional): Event-like object triggering cancellation. Defaults to None.
        sort (bool, optional): Whether to sort scanned files alphabetically. Defaults to True.
        remove_empty_session_dir (bool, optional): Whether to delete an empty session folder
            upon cancellation. Defaults to False.

    Returns:
        dict[str, Any]: Summary dictionary containing execution statistics.
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    # State used by the handlers is initialised before any step that can fail
    stats: dict[str, Any] = {
        "total_files": 0,
        "success": 0,
        "failed": 0,
        "elapsed_seconds": 0.0,
        "original_bytes": 0,
        "compressed_bytes": 0,
        "cancelled": False,
        "cleaned_files_count": 0,
    }
    start_time = time.perf_counter()
    created_destination_files: list[Path] = []
    pre_existing_destination_files: set[Path] = set()
    # Stays None until the session folder exists (scanning or creation may fail first)
    session_out_dir: Path | None = None

    try:
        # Scan input directory for valid files
        discovered_files = scanner(input_path)
        if sort:
            discovered_files = sorted(
                discovered_files, key=lambda p: p.as_posix().casefold()
            )

        total_files = len(discovered_files)
        stats["total_files"] = total_files

        if total_files == 0:
            logger.warning(f"No valid files found in '{input_path}'.")
            stats["no_files"] = True
            return stats

        session_out_dir = create_unique_output_dir(output_path, session_name)

        for index, src_file in enumerate(discovered_files, start=1):
            if cancel_event and cancel_event.is_set():
                raise InterruptedError("Processamento cancelado pelo usuário.")

            success = False
            orig_size = 0
            comp_size = 0
            # Per-file tracking state: reset every iteration so a failure while
            # building this file's destination never reuses the previous path.
            dst_file: Path | None = None
            dst_preexisted: bool | None = None

            try:
                dst_file = build_destination(src_file, session_out_dir)

                # Record files that already existed before processing this batch item
                dst_preexisted = dst_file.exists()
                if dst_preexisted:
                    pre_existing_destination_files.add(dst_file)

                try:
                    orig_size = src_file.stat().st_size
                except OSError:
                    orig_size = 0
                stats["original_bytes"] += orig_size

                # Emit initial progress before processing to allow live intra-file tracking
                if progress_callback:
                    start_info = ProgressInfo(
                        current=index,
                        total=total_files,
                        start_time=start_time,
                        file_path=src_file,
                        success=False,
                        orig_bytes=orig_size,
                        comp_bytes=0,
                        is_completed=False,
                    )
                    _emit_progress(progress_callback, start_info)

                success = process_file(src_file, dst_file)

                if success and dst_file.exists():
                    created_destination_files.append(dst_file)
                    comp_size = dst_file.stat().st_size
                    stats["compressed_bytes"] += comp_size
            except InterruptedError:
                # Cancellation is not a file failure: let the outer handler clean up.
                # Register a known-new output first (OSError-safe, never replaces this).
                if dst_file is not None and dst_preexisted is False:
                    _track_new_output(dst_file, created_destination_files)
                raise
            except _ProgressCallbackError:
                # Progress UI failure, not a file failure: abort at batch level
                raise
            except Exception:
                logger.exception(f"Failed to process file '{src_file}'")
                success = False
                # A failed file may still have left a new (possibly partial) output
                # behind. Keep it eligible for cancellation cleanup, but only when we
                # positively know the destination did not exist before processing.
                if dst_file is not None and dst_preexisted is False:
                    _track_new_output(dst_file, created_destination_files)

            if success:
                stats["success"] += 1
            else:
                stats["failed"] += 1

            # Emit end-of-file progress after completion
            if progress_callback:
                progress_info = ProgressInfo(
                    current=index,
                    total=total_files,
                    start_time=start_time,
                    file_path=src_file,
                    success=success,
                    orig_bytes=orig_size,
                    comp_bytes=comp_size,
                    is_completed=True,
                )
                _emit_progress(progress_callback, progress_info)

        stats["elapsed_seconds"] = round(time.perf_counter() - start_time, 2)
        return stats

    except InterruptedError:
        logger.info(f"Batch processing cancelled by user: '{input_path}'")
        stats["cancelled"] = True

        # Cancelled before the session folder existed: nothing was created to clean
        cleaned_count = 0
        if session_out_dir is not None:
            cleaned_count = safe_cleanup_session_files(
                created_files=created_destination_files,
                session_out_dir=session_out_dir,
                remove_empty_session_dir=remove_empty_session_dir,
                pre_existing_files=pre_existing_destination_files,
            )

        stats["cleaned_files_count"] = cleaned_count
        stats["elapsed_seconds"] = round(time.perf_counter() - start_time, 2)
        return stats

    except Exception as exc:
        logger.exception(f"Failed to process batch for directory '{input_path}'")
        error = exc.original if isinstance(exc, _ProgressCallbackError) else exc
        stats["error"] = str(error) or type(error).__name__
        stats["elapsed_seconds"] = round(time.perf_counter() - start_time, 2)
        return stats
