import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.audio.audio_file_conversion import file_converter
from src.audio.utils.audio_scanner import scan_audio_files
from src.utils.batch_runner import run_batch
from src.utils.output_naming import unique_conversion_output_path
from src.utils.progress import BatchProgressBridge, ProgressInfo

logger = logging.getLogger(__name__)


def directory_converter(
    input_dir: Path,
    output_dir: Path,
    target_format: str,
    progress_callback: Callable[[ProgressInfo], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    """Scans an input directory for audio files and converts each file to target_format.

    Preserves relative subdirectory structure, dispatches intra-file and batch
    progress updates, supports cancellation, and cleans up session artifacts on abort.
    A failure on one file never aborts the batch.

    Args:
        input_dir (Path): Path to the source directory containing audio files.
        output_dir (Path): Path to the destination directory where converted
            audio files will be saved.
        target_format (str): Desired output format (e.g., 'mp3', 'm4a', 'opus',
            'ogg', 'flac', 'wav').
        progress_callback (Callable[[ProgressInfo], None] | None, optional):
            Callback function invoked during and after processing each file.
            Defaults to None.
        cancel_event (threading.Event | None, optional): Event triggering batch
            cancellation. Defaults to None.

    Returns:
        dict[str, Any]: Summary dictionary containing conversion statistics.
    """
    target_fmt = target_format.lower().lstrip(".")
    reserved_paths: set[str] = set()
    bridge = BatchProgressBridge(progress_callback)

    def process_file(src: Path, dst: Path) -> bool:
        return file_converter(
            input_path=src,
            output_path=dst,
            target_format=target_fmt,
            cancel_event=cancel_event,
            file_progress_callback=bridge.on_file_progress,
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
        scanner=scan_audio_files,
        process_file=process_file,
        build_destination=build_destination,
        progress_callback=bridge.on_batch_progress,
        cancel_event=cancel_event,
        sort=True,
        remove_empty_session_dir=True,
    )
