from pathlib import Path


def unique_conversion_output_path(
    input_path: Path,
    output_dir: Path,
    target_format: str,
    reserved_paths: set[str] | None = None,
    relative_path: Path | None = None,
    allow_overwrite: bool = False,
) -> Path:
    """Generates a target output path for converted files.

    Checks disk existence and reserved set entries to prevent name collisions.
    When allow_overwrite is True, candidates existing on disk are accepted directly
    instead of forcing unique numeric suffixes.

    Args:
        input_path (Path): Path to the source file.
        output_dir (Path): Base destination output directory.
        target_format (str): Desired target extension/format name.
        reserved_paths (set[str] | None, optional): Set of reserved case-folded paths. Defaults to None.
        relative_path (Path | None, optional): Relative path hierarchy inside output_dir. Defaults to None.
        allow_overwrite (bool, optional): Whether existing paths on disk may be targeted. Defaults to False.

    Returns:
        Path: Computed output path candidate.
    """
    target_fmt = target_format.lower().lstrip(".")
    relative = relative_path if relative_path is not None else input_path.name
    parent = output_dir / Path(relative).parent
    stem = input_path.stem
    reserved = reserved_paths if reserved_paths is not None else set()

    candidate = parent / f"{stem}_converted.{target_fmt}"
    key = str(candidate.resolve()).casefold()

    if not allow_overwrite and (candidate.exists() or key in reserved):
        source_ext = input_path.suffix.lower().lstrip(".") or "file"
        candidate = parent / f"{stem}_{source_ext}_converted.{target_fmt}"
        key = str(candidate.resolve()).casefold()
        index = 2
        while candidate.exists() or key in reserved:
            candidate = parent / f"{stem}_{source_ext}_converted_{index}.{target_fmt}"
            key = str(candidate.resolve()).casefold()
            index += 1

    reserved.add(key)
    return candidate


def unique_compression_output_path(
    input_path: Path,
    output_dir: Path,
    reserved_paths: set[str] | None = None,
    relative_path: Path | None = None,
    allow_overwrite: bool = False,
) -> Path:
    """Generates a target output path for compressed files.

    Checks disk existence and reserved set entries to prevent name collisions.
    When allow_overwrite is True, candidates existing on disk are accepted directly
    instead of forcing unique numeric suffixes.

    Args:
        input_path (Path): Path to the source file.
        output_dir (Path): Base destination output directory.
        reserved_paths (set[str] | None, optional): Set of reserved case-folded paths. Defaults to None.
        relative_path (Path | None, optional): Relative path hierarchy inside output_dir. Defaults to None.
        allow_overwrite (bool, optional): Whether existing paths on disk may be targeted. Defaults to False.

    Returns:
        Path: Computed output path candidate.
    """
    ext = input_path.suffix.lower().lstrip(".")
    relative = relative_path if relative_path is not None else input_path.name
    parent = output_dir / Path(relative).parent
    stem = input_path.stem
    reserved = reserved_paths if reserved_paths is not None else set()

    candidate = parent / (f"{stem}_compressed.{ext}" if ext else f"{stem}_compressed")
    key = str(candidate.resolve()).casefold()

    if not allow_overwrite and (candidate.exists() or key in reserved):
        index = 2
        while candidate.exists() or key in reserved:
            candidate = (
                parent / f"{stem}_compressed_{index}.{ext}"
                if ext
                else parent / f"{stem}_compressed_{index}"
            )
            key = str(candidate.resolve()).casefold()
            index += 1

    reserved.add(key)
    return candidate