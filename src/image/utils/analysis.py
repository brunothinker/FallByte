from pathlib import Path
from typing import Any

UNCOMPRESSIBLE_FORMATS = {"BMP", "PPM", "GIF"}


def analyze_compression_eligibility(file_paths: list[Path]) -> dict[str, Any]:
    """Analyzes image files to determine compression compatibility.

    Categorizes files into compressible and uncompressible formats based on
    extension to build pre-flight inspection summaries for UI feedback.

    Args:
        file_paths (list[Path]): List of input file paths to analyze.

    Returns:
        dict[str, Any]: Summary dictionary containing execution metrics:
            - total_files (int): Total number of evaluated paths.
            - compressible_count (int): Number of files eligible for compression.
            - uncompressible_count (int): Number of files in lossless/unsupported formats.
            - uncompressible_formats (list[str]): Unique extension list of uncompressible files.
            - is_fully_uncompressible (bool): True if all input files cannot be compressed.
            - has_mixed_formats (bool): True if input contains both compressible and uncompressible files.
    """
    compressible_files = []
    uncompressible_files = []

    for file_path in file_paths:
        ext = file_path.suffix.lstrip(".").upper()
        if ext in ("JPG", "JPEG"):
            ext = "JPEG"

        if ext in UNCOMPRESSIBLE_FORMATS:
            uncompressible_files.append(file_path)
        else:
            compressible_files.append(file_path)

    total = len(file_paths)
    uncompressible_count = len(uncompressible_files)

    return {
        "total_files": total,
        "compressible_count": len(compressible_files),
        "uncompressible_count": uncompressible_count,
        "uncompressible_formats": list(
            {f.suffix.lstrip(".").upper() for f in uncompressible_files}
        ),
        "is_fully_uncompressible": total > 0 and uncompressible_count == total,
        "has_mixed_formats": 0 < uncompressible_count < total,
    }