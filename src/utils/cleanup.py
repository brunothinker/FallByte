import logging
import os
import shutil
import tempfile
from collections.abc import Iterable
from pathlib import Path

# Setup module logger
logger = logging.getLogger(__name__)


def copy_original_file_atomically(
    input_path: Path, output_path: Path, reason: str
) -> bool:
    """Copies a source file untouched to the destination via atomic replace.

    Ensures pre-existing files are never corrupted and no partial files are left behind
    if an interruption occurs during copy.

    Args:
        input_path (Path): Path to the source file.
        output_path (Path): Destination path where the file will be saved.
        reason (str): Context description explaining why the original file is kept.

    Returns:
        bool: True if copy succeeded, False otherwise.
    """
    tmp_path = None
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=output_path.parent,
            prefix=f".{output_path.stem}_tmp_",
            suffix=output_path.suffix,
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)

        shutil.copy2(input_path, tmp_path)
        os.replace(tmp_path, output_path)
        logger.info(f"'{input_path.name}' kept as-is: {reason}.")
        return True
    except Exception as e:
        logger.error(
            f"Failed to copy original file for '{input_path.name}': {e}"
        )
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return False


def safe_cleanup_session_files(
    created_files: Iterable[Path | str],
    root_output_dir: Path | str | None = None,
    session_out_dir: Path | str | None = None,
    remove_empty_session_dir: bool = False,
    pre_existing_files: Iterable[Path | str] | None = None,
) -> int:
    """Safely removes files created during a cancelled processing session.

    Ensures that pre-existing files remain untouched while purging output files
    generated during the interrupted batch session. Only files registered in
    created_files that did NOT exist before the session started are deleted.

    Args:
        created_files (Iterable[Path | str]): File paths generated in the active session.
        root_output_dir (Path | str | None, optional): Base output directory (legacy arg).
        session_out_dir (Path | str | None, optional): Output directory path reserved for the session.
        remove_empty_session_dir (bool, optional): Whether to delete target folder
            if no files remain inside it. Defaults to False.
        pre_existing_files (Iterable[Path | str] | None, optional): File paths that
            already existed prior to the session start. Defaults to None.

    Returns:
        int: Total number of files successfully deleted during cleanup.
    """
    cleaned_count = 0
    target_dir = session_out_dir if session_out_dir is not None else root_output_dir
    base_path = Path(target_dir) if target_dir is not None else None
    affected_dirs = set()

    pre_existing_set = (
        {str(Path(p).resolve()).casefold() for p in pre_existing_files}
        if pre_existing_files is not None
        else set()
    )

    for dst_file in created_files:
        file_path = Path(dst_file)
        file_key = str(file_path.resolve()).casefold()

        # Never delete files that pre-existed before the batch session started
        if file_key in pre_existing_set:
            logger.info(
                f"Preserving pre-existing file from deletion: '{file_path}'"
            )
            continue

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