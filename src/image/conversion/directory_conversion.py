import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.image.conversion.file_conversion import file_converter
from src.image.utils.image_cleanup import safe_cleanup_session_files
from src.image.utils.image_progress import ProgressInfo
from src.image.utils.image_scanner import scan_image_files

# Setup module logger
logger = logging.getLogger(__name__)


def directory_converter(
    input_dir: Path,
    output_dir: Path,
    target_format: str,
    transparency_replacement_color: str = "#FFFFFF",
    progress_callback: Callable[[ProgressInfo], None] | None = None,
) -> dict[str, Any]:
    """Scans an input directory for image files and converts each file to target format.

    Preserves directory tree hierarchy relative to input_dir, dispatches real-time
    progress updates to caller callbacks, handles cancellation signals, and performs
    cleanup of generated session files.

    Args:
        input_dir (Path): Path to the source directory containing images.
        output_dir (Path): Path to the destination directory where converted
            images will be saved.
        target_format (str): Desired output format (e.g., 'jpeg', 'png', 'webp').
        transparency_replacement_color (str, optional): Hex color used to replace
            transparency if target format lacks alpha support. Defaults to "#FFFFFF".
        progress_callback (Callable[[ProgressInfo], None] | None, optional): Callback
            function invoked after processing each file. Defaults to None.

    Returns:
        dict[str, Any]: Summary dictionary containing conversion statistics:
            - success (int): Count of successfully converted files.
            - failed (int): Count of files that failed processing.
            - elapsed_seconds (float): Total elapsed processing duration in seconds.
            - original_bytes (int): Total size of input files in bytes.
            - compressed_bytes (int): Total size of output converted files in bytes.
            - cancelled (bool): True if operation was interrupted by user.
            - cleaned_files_count (int): Count of files deleted during cancellation cleanup.
    """
    stats = {
        "success": 0,
        "failed": 0,
        "elapsed_seconds": 0.0,
        "original_bytes": 0,
        "compressed_bytes": 0,
        "cancelled": False,
        "cleaned_files_count": 0,
    }
    start_time = time.perf_counter()
    created_destination_files: list[Path] = []

    try:
        # Scan input directory for valid image files
        image_files = scan_image_files(input_dir)
        total_files = len(image_files)

        if total_files == 0:
            logger.warning(f"No valid image files found in '{input_dir}'.")
            return stats

        target_fmt = target_format.lower().lstrip(".")

        # Iterate over discovered files and execute conversion
        for index, file_path in enumerate(image_files, start=1):
            # Preserve directory structure relative to input_dir and change extension
            relative_path = file_path.relative_to(input_dir)
            destination_path = (output_dir / relative_path).with_suffix(
                f".{target_fmt}"
            )

            orig_size = file_path.stat().st_size
            stats["original_bytes"] += orig_size

            # Execute single file conversion
            success = file_converter(
                input_path=file_path,
                output_path=destination_path,
                target_format=target_fmt,
                transparency_replacement_color=transparency_replacement_color,
            )

            comp_size = 0
            if success:
                stats["success"] += 1
                if destination_path.exists():
                    created_destination_files.append(destination_path)
                    comp_size = destination_path.stat().st_size
                    stats["compressed_bytes"] += comp_size
            else:
                stats["failed"] += 1

            # Dispatch progress metrics to callback if provided
            if progress_callback:
                progress_info = ProgressInfo(
                    current=index,
                    total=total_files,
                    start_time=start_time,
                    file_path=file_path,
                    success=success,
                    orig_bytes=orig_size,
                    comp_bytes=comp_size,
                )
                progress_callback(progress_info)

        # Calculate total elapsed time
        stats["elapsed_seconds"] = round(time.perf_counter() - start_time, 2)
        return stats

    except InterruptedError:
        logger.info(f"Directory conversion cancelled by user: '{input_dir}'")
        stats["cancelled"] = True

        # Delegate session cleanup to global utility
        cleaned_count = safe_cleanup_session_files(
            created_files=created_destination_files, root_output_dir=output_dir
        )

        stats["cleaned_files_count"] = cleaned_count
        stats["elapsed_seconds"] = round(time.perf_counter() - start_time, 2)
        return stats

    except OSError as e:
        logger.error(
            f"Failed to convert directory '{input_dir}': {e}", exc_info=True
        )
        return stats