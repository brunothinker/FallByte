import logging
from collections.abc import Iterable
from pathlib import Path

# Setup module logger
logger = logging.getLogger(__name__)


def safe_cleanup_session_files(
    created_files: Iterable[Path | str],
    root_output_dir: Path | str | None = None,
    session_out_dir: Path | str | None = None,
    remove_empty_session_dir: bool = False,
) -> int:
    """Safely removes files created during a cancelled processing session.

    Ensures that pre-existing files remain untouched while purging output files
    generated during the interrupted batch session. Accepts either root_output_dir
    or session_out_dir for full backwards compatibility with legacy calls and tests.

    Args:
        created_files (Iterable[Path | str]): File paths generated in the active session.
        root_output_dir (Path | str | None, optional): Base output directory (legacy arg).
        session_out_dir (Path | str | None, optional): Output directory path reserved for the session.
        remove_empty_session_dir (bool, optional): Whether to delete target folder
            if no files remain inside it. Defaults to False.

    Returns:
        int: Total number of files successfully deleted during cleanup.
    """
    cleaned_count = 0
    target_dir = session_out_dir if session_out_dir is not None else root_output_dir
    base_path = Path(target_dir) if target_dir is not None else None
    affected_dirs = set()

    for dst_file in created_files:
        file_path = Path(dst_file)
        if file_path.exists():
            try:
                if (
                    base_path is not None
                    and file_path.parent != base_path
                    and file_path.parent.is_relative_to(base_path)
                ):
                    affected_dirs.add(file_path.parent)
                file_path.unlink()
                cleaned_count += 1
            except OSError as e:
                logger.warning(
                    f"Failed to remove session file '{file_path}': {e}"
                )

    for folder in sorted(
        affected_dirs, key=lambda p: len(p.parts), reverse=True
    ):
        try:
            if (
                base_path is not None
                and folder != base_path
                and folder.exists()
                and not any(folder.iterdir())
            ):
                folder.rmdir()
        except OSError as e:
            logger.warning(f"Failed to remove empty subfolder '{folder}': {e}")

    if remove_empty_session_dir and base_path is not None and base_path.exists():
        try:
            if not any(base_path.iterdir()):
                base_path.rmdir()
        except OSError as e:
            logger.warning(
                f"Failed to remove empty session folder '{base_path}': {e}"
            )

    return cleaned_count