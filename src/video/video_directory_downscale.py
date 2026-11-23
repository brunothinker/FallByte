import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.utils.batch_runner import run_batch
from src.utils.output_naming import unique_conversion_output_path
from src.utils.progress import BatchProgressBridge, ProgressInfo
from src.video.utils.video_scanner import scan_video_files
from src.video.video_file_downscale import file_downscaler, resolve_target_height

# Setup module logger
logger = logging.getLogger(__name__)


def directory_downscaler(
    input_dir: Path,
    output_dir: Path,
    resolution: str | int = "1080p",
    progress_callback: Callable[[ProgressInfo], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    """Scans an input directory for video files and downscales each file to target resolution.

    Supports real-time progress callbacks, user cancellation, and cleanup of
    generated files. Videos already at or below the target resolution are copied
    without upscaling. A failure on one file never aborts the batch.
    """
    target_height = resolve_target_height(resolution)
    reserved_paths: set[str] = set()
    bridge = BatchProgressBridge(progress_callback)

    def process_file(src: Path, dst: Path) -> bool:
        return file_downscaler(
            input_path=src,
            output_path=dst,
            resolution=target_height,
            cancel_event=cancel_event,
            file_progress_callback=bridge.on_file_progress,
        )

    def build_destination(src_file: Path, session_out_dir: Path) -> Path:
        target_fmt = src_file.suffix.lower().lstrip(".") or "mp4"
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
        session_name="downscaled",
        scanner=scan_video_files,
        process_file=process_file,
        build_destination=build_destination,
        progress_callback=bridge.on_batch_progress,
        cancel_event=cancel_event,
        sort=True,
        remove_empty_session_dir=True,
    )
