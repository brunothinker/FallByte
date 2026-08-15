import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.image.compression.file_compression import file_compressor
from src.image.utils.image_cleanup import safe_cleanup_session_files
from src.image.utils.image_progress import ProgressInfo
from src.image.utils.image_scanner import scan_image_files

# Setup module logger
logger = logging.getLogger(__name__)


def directory_compressor(
    input_dir: Path,
    output_dir: Path,
    quality: int = 80,
    progress_callback: Optional[Callable[[ProgressInfo], None]] = None,
) -> Dict[str, Any]:
    """Scans an input directory for image files, compresses each file, and saves them to output_dir.

    Supports real-time progress callbacks, user cancellation, and cleanup of
    generated files.

    Args:
        input_dir (Path): Path to the source directory containing images.
        output_dir (Path): Path to the destination directory where compressed
          images will be saved.
        quality (int, optional): Compression quality percentage (1-100). Defaults
          to 80.
        progress_callback (Callable[[ProgressInfo], None], optional): Callback
          function invoked after processing each file, receiving a ProgressInfo
          instance. Defaults to None.

    Returns:
        Dict[str, Any]: A summary dictionary containing compression
        statistics, byte sizes, elapsed time, and cancellation state.
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
    created_destination_files: List[Path] = []

    try:
        # Scan input directory for valid image files
        image_files = scan_image_files(input_dir)
        total_files = len(image_files)

        if total_files == 0:
            logger.warning(f"No valid image files found in '{input_dir}'.")
            return stats

        # Iterate over discovered files and execute compression
        for index, file_path in enumerate(image_files, start=1):
            # Preserve directory structure relative to input_dir
            relative_path = file_path.relative_to(input_dir)
            destination_path = output_dir / relative_path

            orig_size = file_path.stat().st_size
            stats["original_bytes"] += orig_size

            # Execute single file compression
            success = file_compressor(
                input_path=file_path,
                output_path=destination_path,
                quality=quality,
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
        logger.info(f"Directory compression cancelled by user: '{input_dir}'")
        stats["cancelled"] = True

        # Delegate session cleanup to global utility
        cleaned_count = safe_cleanup_session_files(
            created_files=created_destination_files, root_output_dir=output_dir
        )

        stats["cleaned_files_count"] = cleaned_count
        stats["elapsed_seconds"] = round(time.perf_counter() - start_time, 2)
        return stats

    except Exception as e:
        logger.error(
            f"Failed to compress directory '{input_dir}': {e}", exc_info=True
        )
        return stats