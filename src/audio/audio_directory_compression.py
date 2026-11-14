import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.audio.audio_file_compression import file_compressor
from src.audio.utils.audio_scanner import scan_audio_files
from src.utils.batch_runner import run_batch
from src.utils.progress import ProgressInfo

logger = logging.getLogger(__name__)


def directory_compressor(
    input_dir: Path,
    output_dir: Path,
    quality: int = 80,
    progress_callback: Callable[[ProgressInfo], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    """Scans an input directory for audio files and compresses each file to output_dir.

    Preserves relative subdirectory structure and original file formats,
    dispatches intra-file and batch progress updates, supports cancellation,
    and cleans up session artifacts on abort.
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
        scanner=scan_audio_files,
        process_file=process_file,
        build_destination=build_destination,
        progress_callback=intercept_progress,
        cancel_event=cancel_event,
        sort=False,
        remove_empty_session_dir=True,
    )