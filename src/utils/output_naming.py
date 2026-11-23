"""Shared output-path helpers.

Naming rule:

* **Single-file** outputs get an operation suffix so the result is never
  mistaken for its source (important when the output may land in the source
  folder):

      conversion   ``_converted``        compression  ``_compressed``
      downscale    ``_{height}p``        extraction   ``_extracted``
      tracks       ``_tracks``           metadata     ``_clean``
      resize       ``_resized``

* **Batch (directory)** outputs keep the original file names and are packed
  inside a session folder (``converted/``, ``compressed/``, ``downscaled/``,
  ``extracted/``, ``normalized/``, ``clean_metadata/``, ``resized/``). The
  folder is what identifies the result, so no suffix is added.
  ``unique_batch_output_path`` only resolves collisions when the extension
  changes (e.g. ``a.png`` and ``a.webp`` both converted to ``jpg``).

Collisions are resolved with numeric suffixes (``_2``, ``_3``...), checking both
the disk and ``reserved_paths`` (case-folded paths already handed out in the
current batch).
"""

from pathlib import Path

CONVERTED_SUFFIX = "_converted"
COMPRESSED_SUFFIX = "_compressed"
EXTRACTED_SUFFIX = "_extracted"
TRACKS_SUFFIX = "_tracks"
METADATA_SUFFIX = "_clean"
RESIZED_SUFFIX = "_resized"


def _path_key(path: Path) -> str:
    return str(path.resolve()).casefold()


def _compose(parent: Path, stem: str, suffix: str, ext: str, index: int | None) -> Path:
    name = f"{stem}{suffix}" + (f"_{index}" if index is not None else "")
    return parent / (f"{name}.{ext}" if ext else name)


def _resolve_candidate(
    parent: Path,
    stem: str,
    suffix: str,
    ext: str,
    reserved: set[str],
    allow_overwrite: bool,
) -> Path:
    """Returns the first free candidate (``stem+suffix``, then ``_2``, ``_3``...) and reserves it."""
    candidate = _compose(parent, stem, suffix, ext, None)
    key = _path_key(candidate)
    if not allow_overwrite:
        index = 2
        while candidate.exists() or key in reserved:
            candidate = _compose(parent, stem, suffix, ext, index)
            key = _path_key(candidate)
            index += 1
    reserved.add(key)
    return candidate


def unique_output_path(
    input_path: Path,
    output_dir: Path,
    suffix: str,
    target_format: str | None = None,
    reserved_paths: set[str] | None = None,
    relative_path: Path | None = None,
    allow_overwrite: bool = False,
) -> Path:
    """Generates a collision-free output path ``<stem><suffix>.<ext>``.

    Checks disk existence and reserved set entries to prevent name collisions.
    When allow_overwrite is True, a candidate existing on disk is accepted
    directly instead of forcing a numeric suffix.

    Args:
        input_path (Path): Path to the source file.
        output_dir (Path): Base destination output directory.
        suffix (str): Operation suffix appended to the stem (e.g. ``"_clean"``).
        target_format (str | None, optional): Output extension. Defaults to the
            source extension.
        reserved_paths (set[str] | None, optional): Set of reserved case-folded
            paths, updated in place. Defaults to None.
        relative_path (Path | None, optional): Relative path hierarchy inside
            output_dir. Defaults to None.
        allow_overwrite (bool, optional): Whether existing paths on disk may be
            targeted. Defaults to False.

    Returns:
        Path: Computed output path candidate.
    """
    ext = (
        (target_format if target_format is not None else input_path.suffix)
        .lower()
        .lstrip(".")
    )
    relative = relative_path if relative_path is not None else input_path.name
    parent = output_dir / Path(relative).parent
    reserved = reserved_paths if reserved_paths is not None else set()
    return _resolve_candidate(
        parent, input_path.stem, suffix, ext, reserved, allow_overwrite
    )


def unique_conversion_output_path(
    input_path: Path,
    output_dir: Path,
    target_format: str,
    reserved_paths: set[str] | None = None,
    relative_path: Path | None = None,
    allow_overwrite: bool = False,
) -> Path:
    """Generates a target output path for converted files (``_converted``).

    Follows the same collision rule as every other single-file helper:
    ``name_converted.ext``, then ``name_converted_2.ext``, ``_3``...
    """
    return unique_output_path(
        input_path,
        output_dir,
        CONVERTED_SUFFIX,
        target_format,
        reserved_paths,
        relative_path,
        allow_overwrite,
    )


def unique_compression_output_path(
    input_path: Path,
    output_dir: Path,
    reserved_paths: set[str] | None = None,
    relative_path: Path | None = None,
    allow_overwrite: bool = False,
) -> Path:
    """Generates a target output path for compressed files (``_compressed``)."""
    return unique_output_path(
        input_path,
        output_dir,
        COMPRESSED_SUFFIX,
        None,
        reserved_paths,
        relative_path,
        allow_overwrite,
    )


def unique_downscale_output_path(
    input_path: Path,
    output_dir: Path,
    target_height: int,
    target_format: str | None = None,
    reserved_paths: set[str] | None = None,
    relative_path: Path | None = None,
    allow_overwrite: bool = False,
) -> Path:
    """Generates a target output path for downscaled videos (``_1080p``, ``_720p``...).

    ``target_height`` must be the already-resolved height in pixels.
    """
    return unique_output_path(
        input_path,
        output_dir,
        f"_{int(target_height)}p",
        target_format,
        reserved_paths,
        relative_path,
        allow_overwrite,
    )


def unique_extraction_output_path(
    input_path: Path,
    output_dir: Path,
    target_format: str,
    reserved_paths: set[str] | None = None,
    relative_path: Path | None = None,
    allow_overwrite: bool = False,
) -> Path:
    """Generates a target output path for extracted audio (``_extracted``)."""
    return unique_output_path(
        input_path,
        output_dir,
        EXTRACTED_SUFFIX,
        target_format,
        reserved_paths,
        relative_path,
        allow_overwrite,
    )


def unique_tracks_output_path(
    input_path: Path,
    output_dir: Path,
    target_format: str | None = None,
    reserved_paths: set[str] | None = None,
    relative_path: Path | None = None,
    allow_overwrite: bool = False,
) -> Path:
    """Generates a target output path for track-selection remuxes (``_tracks``)."""
    return unique_output_path(
        input_path,
        output_dir,
        TRACKS_SUFFIX,
        target_format,
        reserved_paths,
        relative_path,
        allow_overwrite,
    )


def unique_metadata_output_path(
    input_path: Path,
    output_dir: Path,
    target_format: str | None = None,
    reserved_paths: set[str] | None = None,
    relative_path: Path | None = None,
    allow_overwrite: bool = False,
) -> Path:
    """Generates a target output path for metadata-free images (``_clean``)."""
    return unique_output_path(
        input_path,
        output_dir,
        METADATA_SUFFIX,
        target_format,
        reserved_paths,
        relative_path,
        allow_overwrite,
    )


def unique_resize_output_path(
    input_path: Path,
    output_dir: Path,
    target_format: str | None = None,
    reserved_paths: set[str] | None = None,
    relative_path: Path | None = None,
    allow_overwrite: bool = False,
) -> Path:
    """Generates a target output path for resized images (``_resized``)."""
    return unique_output_path(
        input_path,
        output_dir,
        RESIZED_SUFFIX,
        target_format,
        reserved_paths,
        relative_path,
        allow_overwrite,
    )


def unique_batch_output_path(
    input_path: Path,
    output_dir: Path,
    target_format: str | None = None,
    reserved_paths: set[str] | None = None,
    relative_path: Path | None = None,
    allow_overwrite: bool = False,
) -> Path:
    """Generates an output path for batch processing that keeps the original name.

    No operation suffix is added: the session folder already identifies the
    result. Numeric suffixes (``_2``, ``_3``...) are only used on collisions,
    which can happen when different sources map to the same target
    (``a.png`` and ``a.webp`` converted to ``jpg``).
    """
    return unique_output_path(
        input_path,
        output_dir,
        "",
        target_format,
        reserved_paths,
        relative_path,
        allow_overwrite,
    )
