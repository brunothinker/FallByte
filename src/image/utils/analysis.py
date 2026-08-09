from pathlib import Path
from typing import List, Dict


UNCOMPRESSIBLE_FORMATS = {"BMP", "PPM", "GIF"}


def analyze_compression_eligibility(file_paths: List[Path]) -> Dict[str, any]:
    """
    Analyzes a list of image files and categorizes them into compressible
    and uncompressible formats to display pre-flight warnings in the UI.
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
        "uncompressible_formats": list({f.suffix.lstrip(".").upper() for f in uncompressible_files}),
        "is_fully_uncompressible": total > 0 and uncompressible_count == total,
        "has_mixed_formats": uncompressible_count > 0 and uncompressible_count < total,
    }