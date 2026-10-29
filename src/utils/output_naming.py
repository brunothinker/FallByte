from pathlib import Path


def unique_conversion_output_path(
    input_path: Path,
    output_dir: Path,
    target_format: str,
    reserved_paths: set[str] | None = None,
    relative_path: Path | None = None,
) -> Path:
    target_fmt = target_format.lower().lstrip(".")
    relative = relative_path if relative_path is not None else input_path.name
    parent = output_dir / Path(relative).parent
    stem = input_path.stem
    reserved = reserved_paths if reserved_paths is not None else set()

    candidate = parent / f"{stem}_converted.{target_fmt}"
    key = str(candidate.resolve()).casefold()
    if candidate.exists() or key in reserved:
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
