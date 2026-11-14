import logging
from pathlib import Path

from src.formats import SUPPORTED_AUDIO_EXTENSIONS

# Setup module logger
logger = logging.getLogger(__name__)


def scan_audio_files(directory_path: Path, recursive: bool = True) -> list[Path]:
    """Scans a directory for supported audio files compatible with FFmpeg.

    Args:
        directory_path (Path): Path to the target directory to scan.
        recursive (bool, optional): If True, scans subdirectories recursively.
            Defaults to True.

    Returns:
        list[Path]: Sorted list of Path objects representing valid discovered audio files.
    """
    discovered_files: list[Path] = []

    try:
        # Validate target directory existence and type
        if not directory_path.exists() or not directory_path.is_dir():
            logger.warning(
                f"Invalid directory path provided for audio scanning: '{directory_path}'"
            )
            return discovered_files

        # Choose recursive or top-level search pattern
        pattern = "**/*" if recursive else "*"

        # Iterate over directory entries and filter by valid audio extensions
        for item in directory_path.glob(pattern):
            if item.is_file() and item.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS:
                discovered_files.append(item)

        # Sort files alphabetically for deterministic processing order
        discovered_files.sort()

        logger.info(
            f"Scanned directory '{directory_path.name}': "
            f"found {len(discovered_files)} supported audio file(s)."
        )
        return discovered_files

    except OSError as e:
        logger.error(
            f"Error occurred while scanning directory '{directory_path}': {e}",
            exc_info=True,
        )
        return discovered_files