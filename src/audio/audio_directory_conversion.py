import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.audio.audio_file_conversion import file_converter
from src.audio.utils.audio_scanner import scan_audio_files
from src.utils.batch_runner import run_batch
from src.utils.output_naming import unique_conversion_output_path
from src.utils.progress import ProgressInfo

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
    """
    target_fmt = target_format.lower().lstrip(".")
    reserved_paths: set[str] = set()
    active_progress_info: ProgressInfo | None = None

    def process_file(src: Path, dst: Path) -> bool:
        def file_progress_cb(
            duration: float, processed: float, fps: float, speed: float
        ) -> None:
            if active_progress_info and progress_callback:
                active_progress_info.duration_seconds = duration
                active_progress_info.processed_seconds = processed
                active_progress_info.fps = fps
                active_progress_info.speed = speed
                progress_callback(active_progress_info)

        return file_converter(
            input_path=src,
            output_path=dst,
            target_format=target_fmt,
            cancel_event=cancel_event,
            file_progress_callback=file_progress_cb,
        )

    def build_destination(src_file: Path, session_out_dir: Path) -> Path:
        return unique_conversion_output_path(
            input_path=src_file,
            output_dir=session_out_dir,
            target_format=target_fmt,
            reserved_paths=reserved_paths,
            relative_path=src_file.relative_to(input_dir),
        )

    def intercept_progress(info: ProgressInfo) -> None:
        nonlocal active_progress_info
        active_progress_info = info
        if progress_callback:
            progress_callback(info)

    return run_batch(
        input_dir=input_dir,
        output_dir=output_dir,
        session_name="converted",
        scanner=scan_audio_files,
        process_file=process_file,
        build_destination=build_destination,
        progress_callback=intercept_progress,
        cancel_event=cancel_event,
        sort=True,
        remove_empty_session_dir=True,
    )