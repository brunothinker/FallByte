"""Helpers that expose the file formats each module accepts, for UI messages.

The lists are derived from the scanners (the single source of truth for which
extensions are actually picked up from a folder), so the UI never drifts out
of sync with the processing code.
"""

from src.formats import (
    AUDIO_TARGET_FORMATS,
    SUPPORTED_AUDIO_EXTENSIONS,
    SUPPORTED_IMAGE_EXTENSIONS,
    SUPPORTED_VIDEO_EXTENSIONS,
    UNCOMPRESSIBLE_AUDIO_FORMATS,
    UNCOMPRESSIBLE_FORMATS,
)


def _to_names(extensions: set[str]) -> list[str]:
    """Converts extensions like '.jpg' into sorted, upper-case names like 'JPG'."""
    return sorted({ext.lstrip(".").upper() for ext in extensions})


def image_input_formats() -> list[str]:
    """Image formats accepted as input by the image conversion module."""
    return _to_names(SUPPORTED_IMAGE_EXTENSIONS)


def image_compression_formats() -> list[str]:
    """Image formats that are really re-encoded by the compression module."""
    return [
        name
        for name in image_input_formats()
        if name not in UNCOMPRESSIBLE_FORMATS
    ]


def video_input_formats() -> list[str]:
    """Video formats accepted as input by both video modules."""
    return _to_names(SUPPORTED_VIDEO_EXTENSIONS)


def audio_input_formats() -> list[str]:
    """Audio formats accepted as input by the audio conversion module."""
    return _to_names(SUPPORTED_AUDIO_EXTENSIONS)


def audio_output_formats() -> list[str]:
    """Target output formats available in the audio conversion dropdown."""
    return [fmt.upper() for fmt in AUDIO_TARGET_FORMATS]


def audio_compression_formats() -> list[str]:
    """Audio formats that are really re-encoded by the compression module."""
    return [
        name
        for name in audio_input_formats()
        if name not in UNCOMPRESSIBLE_AUDIO_FORMATS
    ]


def format_list(formats: list[str]) -> str:
    """Joins format names into a comma separated string for display."""
    return ", ".join(formats)