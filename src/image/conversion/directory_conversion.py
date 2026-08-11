import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.image.conversion.file_conversion import file_converter
from src.utils.progress import ProgressInfo
from src.utils.scanner import scan_image_files

# Setup module logger
logger = logging.getLogger(__name__)


def directory_converter(
    input_dir: Path,
    output_dir: Path,
    target_format: str,
    transparency_replacement_color: str = "#FFFFFF",
    progress_callback: Optional[Callable[[ProgressInfo], None]] = None,
) -> Dict[str, Any]:
    """Scans an input directory for images, converts each one to a target format, and saves them to output_dir.

    Supports real-time progress callbacks, user cancellation, and cleanup of
    generated files.

    Args:
        input_dir (Path): Path to the source directory containing images.
        output_dir (Path): Path to the destination directory where converted
          images will be saved.
        target_format (str): Desired output format (e.g., 'JPEG', 'PNG',
          'WEBP').
        transparency_replacement_color (str, optional): Hex color code used to
          replace the Alpha channel if target format does not support
          transparency. Defaults to "#FFFFFF".
        progress_callback (Callable[[ProgressInfo], None], optional): Callback
          function invoked after each file is processed, receiving a
          ProgressInfo object for UI updates. Defaults to None.

    Returns:
        Dict[str, Any]: A summary dictionary containing execution statistics,
        error logs, and cancellation state.
    """
    stats = {
        "success": 0,
        "failed": 0,
        "total_files": 0,
        "elapsed_seconds": 0.0,
        "cancelled": False,
        "cleaned_files_count": 0,
        "errors": [],
    }
    start_time = time.perf_counter()
    created_destination_files: List[Path] = []

    try:
        # Scan input directory for supported image files
        image_files = scan_image_files(input_dir)
        total_files = len(image_files)
        stats["total_files"] = total_files

        if total_files == 0:
            logger.warning(f"No valid image files found in '{input_dir}'.")
            return stats

        target_fmt = target_format.lower().strip(".")

        # Iterate over discovered files and execute conversion
        for index, file_path in enumerate(image_files, start=1):
            # Preserve subfolder structure inside output_dir
            relative_path = file_path.relative_to(input_dir)
            destination_path = (output_dir / relative_path).with_suffix(
                f".{target_fmt}"
            )

            # Ensure parent subdirectories exist
            destination_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert individual file
            success = file_converter(
                input_path=file_path,
                output_path=destination_path,
                target_format=target_fmt,
                transparency_replacement_color=transparency_replacement_color,
            )

            # Track processing metrics and output references
            if success:
                stats["success"] += 1
                if destination_path.exists():
                    created_destination_files.append(destination_path)
            else:
                stats["failed"] += 1
                stats["errors"].append({
                    "file": file_path.name,
                    "error": "Failed to convert image",
                })

            # Dispatch progress metrics to caller (UI/CLI) if callback is provided
            if progress_callback:
                progress_info = ProgressInfo(
                    current=index,
                    total=total_files,
                    start_time=start_time,
                    file_path=file_path,
                    success=success,
                )
                progress_callback(progress_info)

        # Calculate final execution metrics
        stats["elapsed_seconds"] = round(time.perf_counter() - start_time, 2)

        logger.info(
            f"Batch conversion finished in {stats['elapsed_seconds']}s. "
            f"Success: {stats['success']}, Failed: {stats['failed']}."
        )
        return stats

    except InterruptedError:
        logger.info(f"Directory conversion cancelled by user: '{input_dir}'")
        stats["cancelled"] = True

        # Clean up files created during this processing session upon user cancellation
        cleaned_count = 0
        affected_dirs = set()

        for dst_file in created_destination_files:
            if dst_file.exists():
                try:
                    if (
                        dst_file.parent != output_dir
                        and dst_file.parent.is_relative_to(output_dir)
                    ):
                        affected_dirs.add(dst_file.parent)
                    dst_file.unlink()
                    cleaned_count += 1
                except Exception as e:
                    logger.warning(f"Failed to remove file {dst_file}: {e}")

        # Purge empty subdirectories left behind in destination
        for folder in sorted(
            affected_dirs, key=lambda p: len(p.parts), reverse=True
        ):
            try:
                if (
                    folder != output_dir
                    and folder.exists()
                    and not any(folder.iterdir())
                ):
                    folder.rmdir()
            except Exception:
                pass

        stats["cleaned_files_count"] = cleaned_count
        stats["elapsed_seconds"] = round(time.perf_counter() - start_time, 2)
        return stats

    except Exception as e:
        logger.error(
            f"Failed to process directory '{input_dir}': {e}", exc_info=True
        )
        stats["elapsed_seconds"] = round(time.perf_counter() - start_time, 2)
        return stats