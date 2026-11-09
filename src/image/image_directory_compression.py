import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.image.image_file_compression import file_compressor
from src.image.utils.image_scanner import scan_image_files
from src.utils.batch_runner import run_batch
from src.utils.progress import ProgressInfo

# Setup module logger
logger = logging.getLogger(__name__)


def directory_compressor(
    input_dir: Path,
    output_dir: Path,
    quality: int = 80,
    progress_callback: Callable[[ProgressInfo], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    """Scans an input directory for image files and compresses each file to output_dir.

    Preserves directory tree hierarchy relative to input_dir, dispatches real-time
    progress updates to caller callbacks, handles cancellation signals, and performs
    cleanup of generated session files. A failure on one file never aborts the batch.

    Args:
        input_dir (Path): Path to the source directory containing images.
        output_dir (Path): Path to the destination directory where compressed
            images will be saved.
        quality (int, optional): Compression quality percentage (1-100).
            Defaults to 80.
        progress_callback (Callable[[ProgressInfo], None] | None, optional): Callback
            function invoked after processing each file. Defaults to None.
        cancel_event (threading.Event | None, optional): Event triggering batch
            cancellation. Defaults to None.

    Returns:
        dict[str, Any]: Summary dictionary containing compression metrics.
    """

    def process_file(src: Path, dst: Path) -> bool:
        return file_compressor(
            input_path=src,
            output_path=dst,
            quality=quality,
        )

    def build_destination(src_file: Path, session_out_dir: Path) -> Path:
        relative_path = src_file.relative_to(input_dir)
        return session_out_dir / relative_path

    return run_batch(
        input_dir=input_dir,
        output_dir=output_dir,
        session_name="compressed",
        scanner=scan_image_files,
        process_file=process_file,
        build_destination=build_destination,
        progress_callback=progress_callback,
        cancel_event=cancel_event,
        sort=False,
        remove_empty_session_dir=False,
    )