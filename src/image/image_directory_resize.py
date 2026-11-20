import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.image.image_file_resize import UNRESIZABLE_FORMATS, file_resizer
from src.image.utils.image_scanner import scan_image_files
from src.utils.batch_runner import run_batch
from src.utils.progress import ProgressInfo

logger = logging.getLogger(__name__)


def directory_resizer(
    input_dir: Path,
    output_dir: Path,
    mode: str = "dimension",
    max_width: int | None = 1920,
    max_height: int | None = 1080,
    percentage: int | None = 50,
    progress_callback: Callable[[ProgressInfo], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    """Scans an input directory for image files and resizes each file to output_dir.

    Preserves directory tree hierarchy relative to input_dir, dispatches real-time
    progress updates to caller callbacks, handles cancellation signals, and performs
    cleanup of generated session files. A failure on one file never aborts the batch.

    Args:
        input_dir (Path): Path to the source directory containing images.
        output_dir (Path): Path to the destination directory where resized
            images will be saved.
        mode (str, optional): Resizing mode ('dimension' or 'percentage').
            Defaults to 'dimension'.
        max_width (int | None, optional): Maximum target width in pixels.
            Defaults to 1920.
        max_height (int | None, optional): Maximum target height in pixels.
            Defaults to 1080.
        percentage (int | None, optional): Scale percentage for 'percentage' mode.
            Defaults to 50.
        progress_callback (Callable[[ProgressInfo], None] | None, optional): Callback
            function invoked after processing each file. Defaults to None.
        cancel_event (threading.Event | None, optional): Event triggering batch
            cancellation. Defaults to None.

    Returns:
        dict[str, Any]: Summary dictionary containing resize execution metrics.
    """

    def process_file(src: Path, dst: Path) -> bool:
        return file_resizer(
            input_path=src,
            output_path=dst,
            mode=mode,
            max_width=max_width,
            max_height=max_height,
            percentage=percentage,
        )

    def build_destination(src_file: Path, session_out_dir: Path) -> Path:
        relative_path = src_file.relative_to(input_dir)
        dst_path = session_out_dir / relative_path
        if dst_path.suffix.lstrip(".").upper() in UNRESIZABLE_FORMATS:
            return dst_path.with_suffix(".png")
        return dst_path

    return run_batch(
        input_dir=input_dir,
        output_dir=output_dir,
        session_name="resized",
        scanner=scan_image_files,
        process_file=process_file,
        build_destination=build_destination,
        progress_callback=progress_callback,
        cancel_event=cancel_event,
        sort=True,
        remove_empty_session_dir=True,
    )
