import logging
import os
import shutil
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from src.utils.file_result import FileResult

# Setup module logger
logger = logging.getLogger(__name__)


def copy_original_file_atomically(
    input_path: Path, output_path: Path, reason_key: str, **params: Any
) -> FileResult:
    """Copies a source file untouched to the destination via atomic replace.

    Ensures pre-existing files are never corrupted and no partial files are left behind
    if an interruption occurs during copy.

    Args:
        input_path (Path): Path to the source file.
        output_path (Path): Destination path where the file will be saved.
        reason_key (str): Locale key explaining why the original file is kept.
            Legacy callers may still pass a plain English sentence; the UI
            translation layer returns unknown keys unchanged.
        **params (Any): Format parameters for the locale key.

    Returns:
        FileResult: ``FileResult.skipped(reason_key, **params)`` if the copy
            succeeded, ``FileResult.failed()`` otherwise.
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
        # Only key and parameters are logged: free text would be colored by keyword.
        logger.info(f"'{input_path.name}' kept as-is [{reason_key}] {params}")
        return FileResult.skipped(reason_key, **params)
    except Exception as e:
        logger.error(f"Failed to copy original file for '{input_path.name}': {e}")
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return FileResult.failed()


def safe_cleanup_session_files(
    created_files: Iterable[Path | str],
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
        session_out_dir (Path | str | None, optional): Output directory path reserved for the session.
        remove_empty_session_dir (bool, optional): Whether to delete target folder
            if no files remain inside it. Defaults to False.
        pre_existing_files (Iterable[Path | str] | None, optional): File paths that
            already existed prior to the session start. Defaults to None.

    Returns:
        int: Total number of files successfully deleted during cleanup.
    """
    cleaned_count = 0
    base_path = Path(session_out_dir) if session_out_dir is not None else None
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
            logger.info(f"Preserving pre-existing file from deletion: '{file_path}'")
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
                logger.warning(f"Failed to remove session file '{file_path}': {e}")

    for folder in sorted(affected_dirs, key=lambda p: len(p.parts), reverse=True):
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
            logger.warning(f"Failed to remove empty session folder '{base_path}': {e}")

    return cleaned_count
