import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.image.image_file_conversion import file_converter
from src.image.utils.image_scanner import scan_image_files
from src.utils.batch_runner import run_batch
from src.utils.output_naming import unique_conversion_output_path
from src.utils.progress import ProgressInfo

# Setup module logger
logger = logging.getLogger(__name__)


def directory_converter(
    input_dir: Path,
    output_dir: Path,
    target_format: str,
    transparency_replacement_color: str = "#FFFFFF",
    progress_callback: Callable[[ProgressInfo], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    """Scans an input directory for image files and converts each file to target format.

    Preserves directory tree hierarchy relative to input_dir, dispatches real-time
    progress updates to caller callbacks, handles cancellation signals, and performs
    cleanup of generated session files. A failure on one file never aborts the batch.

    Args:
        input_dir (Path): Path to the source directory containing images.
        output_dir (Path): Path to the destination directory where converted
            images will be saved.
        target_format (str): Desired output format (e.g., 'jpeg', 'png', 'webp').
        transparency_replacement_color (str, optional): Hex color used to replace
            transparency if target format lacks alpha support. Defaults to "#FFFFFF".
        progress_callback (Callable[[ProgressInfo], None] | None, optional): Callback
            function invoked after processing each file. Defaults to None.
        cancel_event (threading.Event | None, optional): Event triggering batch
            cancellation. Defaults to None.

    Returns:
        dict[str, Any]: Summary dictionary containing conversion statistics.
    """
    target_fmt = target_format.lower().lstrip(".")
    reserved_paths: set[str] = set()

    def process_file(src: Path, dst: Path) -> bool:
        return file_converter(
            input_path=src,
            output_path=dst,
            target_format=target_fmt,
            transparency_replacement_color=transparency_replacement_color,
        )

    def build_destination(src_file: Path, session_out_dir: Path) -> Path:
        return unique_conversion_output_path(
            input_path=src_file,
            output_dir=session_out_dir,
            target_format=target_fmt,
            reserved_paths=reserved_paths,
            relative_path=src_file.relative_to(input_dir),
        )

    return run_batch(
        input_dir=input_dir,
        output_dir=output_dir,
        session_name="converted",
        scanner=scan_image_files,
        process_file=process_file,
        build_destination=build_destination,
        progress_callback=progress_callback,
        cancel_event=cancel_event,
        sort=True,
        remove_empty_session_dir=True,
    )