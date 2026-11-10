import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.utils.batch_runner import run_batch
from src.utils.progress import ProgressInfo
from src.video.utils.video_scanner import scan_video_files
from src.video.video_file_compression import file_compressor

# Setup module logger
logger = logging.getLogger(__name__)


def directory_compressor(
    input_dir: Path,
    output_dir: Path,
    quality: int = 80,
    progress_callback: Callable[[ProgressInfo], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    """Scans an input directory for video files, compresses each file, and saves them to output_dir.

    Supports real-time progress callbacks, user cancellation, and cleanup of
    generated files. Maintains original container formats. A failure on one
    file never aborts the batch.

    Args:
        input_dir (Path): Path to the source directory containing videos.
        output_dir (Path): Path to the destination directory where compressed
          videos will be saved.
        quality (int, optional): Compression quality percentage (1-100). Defaults
          to 80.
        progress_callback (Callable[[ProgressInfo], None], optional): Callback
          function invoked during and after processing each file. Defaults to None.
        cancel_event (threading.Event, optional): Event terminating batch execution.
          Defaults to None.

    Returns:
        Dict[str, Any]: Summary dictionary containing compression statistics.
    """
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

        return file_compressor(
            input_path=src,
            output_path=dst,
            quality=quality,
            cancel_event=cancel_event,
            file_progress_callback=file_progress_cb,
        )

    def build_destination(src_file: Path, session_out_dir: Path) -> Path:
        relative_path = src_file.relative_to(input_dir)
        return session_out_dir / relative_path

    def intercept_progress(info: ProgressInfo) -> None:
        nonlocal active_progress_info
        active_progress_info = info
        if progress_callback:
            progress_callback(info)

    return run_batch(
        input_dir=input_dir,
        output_dir=output_dir,
        session_name="compressed",
        scanner=scan_video_files,
        process_file=process_file,
        build_destination=build_destination,
        progress_callback=intercept_progress,
        cancel_event=cancel_event,
        sort=False,
        remove_empty_session_dir=True,
    )