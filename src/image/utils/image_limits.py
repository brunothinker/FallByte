"""Image pixel limit configuration and DecompressionBombError formatting."""

from __future__ import annotations

import logging
import re
import warnings

from PIL import Image

# Desktop-appropriate ceiling: 250 MP warning threshold, 500 MP hard error ceiling
# (~2 GB max uncompressed RGBA buffer per image) to support high-res panoramas,
# scans, and 3D renders while protecting the host from RAM exhaustion.
DESKTOP_MAX_IMAGE_PIXELS = 250_000_000

_PIXELS_RE = re.compile(r"Image size \((\d+) pixels\)")


def configure_image_pixel_limits() -> None:
    """Applies desktop pixel limits and silences DecompressionBombWarning below hard limit."""
    Image.MAX_IMAGE_PIXELS = DESKTOP_MAX_IMAGE_PIXELS
    warnings.filterwarnings("ignore", category=Image.DecompressionBombWarning)


def format_decompression_bomb_message(
    filename: str, exc: Image.DecompressionBombError
) -> str:
    """Formats a clear user-facing error message with image size in megapixels."""
    match = _PIXELS_RE.search(str(exc))
    if match:
        pixels = int(match.group(1))
        megapixels = pixels / 1_000_000
        return f"{filename}: image too large ({megapixels:.1f} MP)"
    return f"{filename}: image too large"


def log_decompression_bomb_error(
    logger: logging.Logger, filename: str, exc: Image.DecompressionBombError
) -> None:
    """Logs an explicit, user-friendly error when an image exceeds MAX_IMAGE_PIXELS."""
    logger.error(format_decompression_bomb_message(filename, exc))
