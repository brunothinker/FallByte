from pathlib import Path


def get_safe_initial_directory(target_path: Path | str | None = None) -> str:
    """Returns a valid initial directory path for FilePickers.

    If the provided path is None, does not exist, or is not a directory,
    it gracefully falls back to the user's home directory.

    Args:
        target_path (Path | str | None): Target path to validate.

    Returns:
        str: Absolute path string guaranteed to exist.
    """
    if target_path:
        p = Path(target_path)
        # If it points to a file, take its parent directory
        if p.is_file():
            p = p.parent
        if p.exists() and p.is_dir():
            return str(p)

    return str(Path.home())