import logging
from pathlib import Path
from typing import Iterable

# Setup module logger
logger = logging.getLogger(__name__)


def safe_cleanup_session_files(
    created_files: Iterable[Path],
    root_output_dir: Path
) -> int:
    """
    Safely removes files created during a cancelled processing session.

    Ensures that root_output_dir is NEVER deleted, preserving the user's pre-existing files.
    Purges only empty subdirectories created during the current session.

    Args:
        created_files (Iterable[Path]): List or set of file paths generated in the active session.
        root_output_dir (Path): The base destination directory selected by the user.

    Returns:
        int: Total number of files successfully deleted during cleanup.
    """
    cleaned_count = 0
    affected_dirs = set()

    # Delete session files and collect their parent subdirectories
    for dst_file in created_files:
        if dst_file.exists():
            try:
                if dst_file.parent != root_output_dir and dst_file.parent.is_relative_to(root_output_dir):
                    affected_dirs.add(dst_file.parent)
                dst_file.unlink()
                cleaned_count += 1
            except Exception as e:
                logger.warning(f"Failed to remove session file '{dst_file}': {e}")

    # Remove empty created subdirectories from deepest level to shallowest
    for folder in sorted(affected_dirs, key=lambda p: len(p.parts), reverse=True):
        try:
            if folder != root_output_dir and folder.exists() and not any(folder.iterdir()):
                folder.rmdir()
        except Exception as e:
            logger.warning(f"Failed to remove empty subfolder '{folder}': {e}")

    return cleaned_count