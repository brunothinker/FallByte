import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.audio.audio_file_normalization import (
    DEFAULT_LOUDNESS_PRESET,
    file_normalizer,
)
from src.audio.utils.audio_scanner import scan_audio_files
from src.formats import NORMALIZABLE_AUDIO_FORMATS
from src.utils.batch_runner import run_batch
from src.utils.file_result import FileResult
from src.utils.output_naming import unique_batch_output_path
from src.utils.progress import BatchProgressBridge, ProgressInfo

logger = logging.getLogger(__name__)


def scan_normalizable_audio_files(
    directory_path: Path, recursive: bool = True
) -> list[Path]:
    """Scans a directory for audio files eligible for EBU R128 loudness normalization."""
    return [
        path
        for path in scan_audio_files(directory_path, recursive=recursive)
        if path.suffix.lower().lstrip(".") in NORMALIZABLE_AUDIO_FORMATS
    ]


def directory_normalizer(
    input_dir: Path,
    output_dir: Path,
    preset_key: str = DEFAULT_LOUDNESS_PRESET,
    progress_callback: Callable[[ProgressInfo], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    """Normalizes perceived loudness across all supported audio files in a directory.

    Preserves relative subdirectory structure and original file formats inside
    `<output_dir>/normalized/`, dispatches intra-file and batch progress updates,
    supports cancellation, and cleans up session artifacts on abort.

    Args:
        input_dir (Path): Path to the source directory containing audio files.
        output_dir (Path): Path to the destination directory where normalized
            audio files will be saved.
        preset_key (str, optional): Target loudness preset key ('music', 'podcast',
            or 'broadcast'). Defaults to 'music'.
        progress_callback (Callable[[ProgressInfo], None] | None, optional):
            Callback function invoked during and after processing each file.
            Defaults to None.
        cancel_event (threading.Event | None, optional): Event triggering batch
            cancellation. Defaults to None.

    Returns:
        dict[str, Any]: Summary dictionary containing normalization statistics.
    """
    bridge = BatchProgressBridge(progress_callback)

    def process_file(src: Path, dst: Path) -> FileResult:
        return file_normalizer(
            input_path=src,
            output_path=dst,
            preset_key=preset_key,
            cancel_event=cancel_event,
            file_progress_callback=bridge.on_file_progress,
        )

    reserved_paths: set[str] = set()

    def build_destination(src_file: Path, session_out_dir: Path) -> Path:
        return unique_batch_output_path(
            input_path=src_file,
            output_dir=session_out_dir,
            reserved_paths=reserved_paths,
            relative_path=src_file.relative_to(input_dir),
        )

    return run_batch(
        input_dir=input_dir,
        output_dir=output_dir,
        session_name="normalized",
        scanner=scan_normalizable_audio_files,
        process_file=process_file,
        build_destination=build_destination,
        progress_callback=bridge.on_batch_progress,
        cancel_event=cancel_event,
        sort=True,
        remove_empty_session_dir=True,
    )
