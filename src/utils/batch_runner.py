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
    progress tracking metrics, user cancellation signals, and graceful cleanup.

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

    # Scan input directory for valid files
    discovered_files = scanner(input_path)
    if sort:
        discovered_files = sorted(
            discovered_files, key=lambda p: p.as_posix().casefold()
        )

    total_files = len(discovered_files)

    stats: dict[str, Any] = {
        "total_files": total_files,
        "success": 0,
        "failed": 0,
        "elapsed_seconds": 0.0,
        "original_bytes": 0,
        "compressed_bytes": 0,
        "cancelled": False,
        "cleaned_files_count": 0,
    }
    start_time = time.perf_counter()

    if total_files == 0:
        logger.warning(f"No valid files found in '{input_path}'.")
        stats["no_files"] = True
        return stats

    session_out_dir: Path = create_unique_output_dir(output_path, session_name)
    created_destination_files: list[Path] = []

    try:
        for index, src_file in enumerate(discovered_files, start=1):
            if cancel_event and cancel_event.is_set():
                raise InterruptedError("Processamento cancelado pelo usuário.")

            dst_file = build_destination(src_file, session_out_dir)

            try:
                orig_size = src_file.stat().st_size
            except OSError:
                orig_size = 0
            stats["original_bytes"] += orig_size

            success = process_file(src_file, dst_file)
            comp_size = 0

            if success:
                stats["success"] += 1
                if dst_file.exists():
                    created_destination_files.append(dst_file)
                    comp_size = dst_file.stat().st_size
                    stats["compressed_bytes"] += comp_size
            else:
                stats["failed"] += 1

            if progress_callback:
                progress_info = ProgressInfo(
                    current=index,
                    total=total_files,
                    start_time=start_time,
                    file_path=src_file,
                    success=success,
                    orig_bytes=orig_size,
                    comp_bytes=comp_size,
                )
                progress_callback(progress_info)

        stats["elapsed_seconds"] = round(time.perf_counter() - start_time, 2)
        return stats

    except InterruptedError:
        logger.info(f"Batch processing cancelled by user: '{input_path}'")
        stats["cancelled"] = True

        cleaned_count = safe_cleanup_session_files(
            created_files=created_destination_files,
            session_out_dir=session_out_dir,
            remove_empty_session_dir=remove_empty_session_dir,
        )

        stats["cleaned_files_count"] = cleaned_count
        stats["elapsed_seconds"] = round(time.perf_counter() - start_time, 2)
        return stats

    except Exception as e:
        logger.error(
            f"Failed to process batch for directory '{input_path}': {e}",
            exc_info=True,
        )
        stats["elapsed_seconds"] = round(time.perf_counter() - start_time, 2)
        return stats