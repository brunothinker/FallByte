import logging
from pathlib import Path

from src.formats import SUPPORTED_IMAGE_EXTENSIONS

logger = logging.getLogger(__name__)

def scan_image_files(directory_path: Path, recursive: bool = True) -> list[Path]:
    """Scans a directory for supported image files.

    Args:
        directory_path (Path): Path to the target directory to scan.
        recursive (bool, optional): If True, scans subdirectories recursively.
            Defaults to True.

    Returns:
        list[Path]: A list of Path objects representing valid discovered image files.
    """
    discovered_images: list[Path] = []

    try:
        if not directory_path.exists() or not directory_path.is_dir():
            logger.warning(
                f"Invalid directory path provided for scanning: '{directory_path}'"
            )
            return discovered_images

        # Select scanning method based on recursion preference
        pattern = "**/*" if recursive else "*"

        # Iterate over directory items and filter by supported extension
        for item in directory_path.glob(pattern):
            if (
                item.is_file()
                and item.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
            ):
                discovered_images.append(item)

        # Sort paths alphabetically for consistent batch processing
        discovered_images.sort()

        logger.info(
            f"Scanned directory '{directory_path.name}': "
            f"found {len(discovered_images)} supported image file(s)."
        )
        return discovered_images

    except OSError as e:
        logger.error(
            f"Error occurred while scanning directory '{directory_path}': {e}",
            exc_info=True,
        )
        return discovered_images