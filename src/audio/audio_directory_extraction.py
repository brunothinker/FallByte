import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.audio.audio_file_extraction import file_extractor
from src.formats import SUPPORTED_VIDEO_EXTENSIONS
from src.utils.batch_runner import run_batch
from src.utils.output_naming import unique_conversion_output_path
from src.utils.progress import ProgressInfo

logger = logging.getLogger(__name__)


def scan_video_sources(directory_path: Path, recursive: bool = True) -> list[Path]:
    """Scans a directory for supported video files for audio extraction.

    Self-contained inside `src/audio/` so the audio package maintains strict
    architectural isolation from `src/video/`.

    Args:
        directory_path (Path): Path to the target directory to scan.
        recursive (bool, optional): If True, scans subdirectories recursively.
            Defaults to True.

    Returns:
        list[Path]: Sorted list of Path objects representing discovered video files.
    """
    discovered_files: list[Path] = []

    try:
        if not directory_path.exists() or not directory_path.is_dir():
            logger.warning(
                f"Invalid directory path provided for video scanning: '{directory_path}'"
            )
            return discovered_files

        pattern = "**/*" if recursive else "*"

        for item in directory_path.glob(pattern):
            if item.is_file() and item.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS:
                discovered_files.append(item)

        discovered_files.sort()

        logger.info(
            f"Scanned directory '{directory_path.name}': "
            f"found {len(discovered_files)} supported video file(s)."
        )
        return discovered_files

    except OSError:
        logger.exception(f"Error occurred while scanning directory '{directory_path}'")
        return discovered_files


def directory_extractor(
    input_dir: Path,
    output_dir: Path,
    target_format: str,
    progress_callback: Callable[[ProgressInfo], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    """Scans an input directory for video files and extracts each audio track.

    Preserves relative subdirectory structure, avoids filename collisions across
    videos sharing the same stem, dispatches intra-file and batch progress
    updates, supports cancellation, and cleans up session artifacts on abort.
    Videos without audio streams or corrupted files are reported as failed
    without aborting the batch.

    Args:
        input_dir (Path): Path to the source directory containing video files.
        output_dir (Path): Path to the destination directory where extracted
            audio files will be saved.
        target_format (str): Desired output format (e.g., 'mp3', 'm4a', 'opus',
            'ogg', 'flac', 'wav').
        progress_callback (Callable[[ProgressInfo], None] | None, optional):
            Callback function invoked during and after processing each file.
            Defaults to None.
        cancel_event (threading.Event | None, optional): Event triggering batch
            cancellation. Defaults to None.

    Returns:
        dict[str, Any]: Summary dictionary containing extraction statistics.
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

        return file_extractor(
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
        session_name="extracted",
        scanner=scan_video_sources,
        process_file=process_file,
        build_destination=build_destination,
        progress_callback=intercept_progress,
        cancel_event=cancel_event,
        sort=True,
        remove_empty_session_dir=True,
    )
