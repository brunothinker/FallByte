import logging
from pathlib import Path
from typing import List, Set

# Setup module logger
logger = logging.getLogger(__name__)

# Video formats officially supported by the app (same list offered in the UI).
SUPPORTED_VIDEO_EXTENSIONS: Set[str] = {
    ".mp4",
    ".mkv",
    ".webm",
    ".mov",
    ".avi",
    ".wmv",
}


def scan_video_files(
    directory_path: Path, recursive: bool = True
) -> List[Path]:
    """Scans a directory for supported video files compatible with FFmpeg.

    Args:
        directory_path (Path): Path to the target directory to scan.
        recursive (bool, optional): If True, scans subdirectories recursively.
          Defaults to True.

    Returns:
        List[Path]: A list of Path objects representing valid discovered video
        files.
    """
    discovered_videos: List[Path] = []

    try:
        if not directory_path.exists() or not directory_path.is_dir():
            logger.warning(
                "Invalid directory path provided for video scanning:"
                f" '{directory_path}'"
            )
            return discovered_videos

        # Select scanning method based on recursion preference
        pattern = "**/*" if recursive else "*"

        # Iterate over directory items and filter by supported video extension
        for item in directory_path.glob(pattern):
            if (
                item.is_file()
                and item.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS
            ):
                discovered_videos.append(item)

        # Sort paths alphabetically for consistent batch processing
        discovered_videos.sort()

        logger.info(
            f"Scanned directory '{directory_path.name}': "
            f"found {len(discovered_videos)} supported video file(s)."
        )
        return discovered_videos

    except Exception as e:
        logger.error(
            f"Error occurred while scanning directory '{directory_path}': {e}",
            exc_info=True,
        )
        return discovered_videos
