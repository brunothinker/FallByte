import logging
import time
from pathlib import Path
from typing import Dict, Callable, Optional

from src.image.conversion.file_converter import file_converter
from src.utils.progress import ProgressInfo
from src.utils.scanner import scan_image_files

# Setup module logger
logger = logging.getLogger(__name__)


def directory_converter(
        input_dir: Path,
        output_dir: Path,
        target_format: str,
        transparency_replacement_color: str = "#FFFFFF",
        progress_callback: Optional[Callable[[ProgressInfo], None]] = None
) -> Dict[str, any]:
    """
    Scans an input directory for images, converts each one, and saves them to output_dir.

    Args:
        input_dir (Path): Path to the source directory containing images.
        output_dir (Path): Path to the destination directory where converted images will be saved.
        target_format (str): Desired output format (e.g., 'JPEG', 'PNG', 'WEBP').
        transparency_replacement_color (str, optional): Hex color code used to replace
            the Alpha channel if target format does not support transparency.
            Defaults to "#FFFFFF".
        progress_callback (Callable[[ProgressInfo], None], optional): Callback function invoked
            after each file is processed, receiving a ProgressInfo object for UI updates.
            Defaults to None.

    Returns:
        Dict[str, any]: A summary dictionary containing 'success', 'failed', and 'elapsed_seconds'.
    """
    stats = {"success": 0, "failed": 0, "elapsed_seconds": 0.0}
    start_time = time.perf_counter()

    try:
        # Scan input directory for supported image files
        image_files = scan_image_files(input_dir)
        total_files = len(image_files)

        if total_files == 0:
            logger.warning(f"No valid image files found in '{input_dir}'.")
            return stats

        # Iterate over discovered files and execute conversion
        for index, file_path in enumerate(image_files, start=1):
            # Preserve subfolder structure inside output_dir
            relative_path = file_path.relative_to(input_dir)
            destination_path = (output_dir / relative_path).with_suffix(f".{target_format.lower()}")

            # Convert individual file
            success = file_converter(
                input_path=file_path,
                output_path=destination_path,
                target_format=target_format,
                transparency_replacement_color=transparency_replacement_color
            )

            # Track processing metrics
            if success:
                stats["success"] += 1
            else:
                stats["failed"] += 1

            # Dispatch progress metrics to caller (UI/CLI) if callback is provided
            if progress_callback:
                progress_info = ProgressInfo(
                    current=index,
                    total=total_files,
                    start_time=start_time
                )
                progress_callback(progress_info)

        # Calculate final execution metrics
        stats["elapsed_seconds"] = round(time.perf_counter() - start_time, 2)

        logger.info(
            f"Batch conversion finished in {stats['elapsed_seconds']}s. "
            f"Success: {stats['success']}, Failed: {stats['failed']}."
        )
        return stats

    except Exception as e:
        logger.error(f"Failed to process directory '{input_dir}': {e}", exc_info=True)
        return stats