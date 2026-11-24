import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.image.image_file_metadata import (
    UNWRITABLE_METADATA_FORMATS,
    file_metadata_remover,
)
from src.image.utils.image_scanner import scan_image_files
from src.utils.batch_runner import run_batch
from src.utils.file_result import FileResult
from src.utils.output_naming import unique_batch_output_path
from src.utils.progress import ProgressInfo

logger = logging.getLogger(__name__)


def directory_metadata_remover(
    input_dir: Path,
    output_dir: Path,
    progress_callback: Callable[[ProgressInfo], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    """Scans an input directory for image files and strips metadata from each file.

    Preserves directory tree hierarchy relative to input_dir, dispatches real-time
    progress updates to caller callbacks, handles cancellation signals, and performs
    cleanup of generated session files. A failure on one file never aborts the batch.

    Args:
        input_dir (Path): Path to the source directory containing images.
        output_dir (Path): Path to the destination directory where sanitized
            images will be saved.
        progress_callback (Callable[[ProgressInfo], None] | None, optional): Callback
            function invoked after processing each file. Defaults to None.
        cancel_event (threading.Event | None, optional): Event triggering batch
            cancellation. Defaults to None.

    Returns:
        dict[str, Any]: Summary dictionary containing execution metrics.
    """

    def process_file(src: Path, dst: Path) -> FileResult:
        return file_metadata_remover(input_path=src, output_path=dst)

    reserved_paths: set[str] = set()

    def build_destination(src_file: Path, session_out_dir: Path) -> Path:
        ext = src_file.suffix.lstrip(".").upper()
        return unique_batch_output_path(
            input_path=src_file,
            output_dir=session_out_dir,
            target_format="png" if ext in UNWRITABLE_METADATA_FORMATS else None,
            reserved_paths=reserved_paths,
            relative_path=src_file.relative_to(input_dir),
        )

    return run_batch(
        input_dir=input_dir,
        output_dir=output_dir,
        session_name="clean_metadata",
        scanner=scan_image_files,
        process_file=process_file,
        build_destination=build_destination,
        progress_callback=progress_callback,
        cancel_event=cancel_event,
        sort=True,
        remove_empty_session_dir=True,
    )
