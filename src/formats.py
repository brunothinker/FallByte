"""Centralized media format definitions and constants for FallByte."""

# Supported input image extensions (lowercase with leading dot)
SUPPORTED_IMAGE_EXTENSIONS: set[str] = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".tiff",
    ".tif",
    ".gif",
    ".ppm",
    ".ico",
    ".heic",
    ".heif",
}

# Supported input video extensions (lowercase with leading dot)
SUPPORTED_VIDEO_EXTENSIONS: set[str] = {
    ".mp4",
    ".mkv",
    ".webm",
    ".mov",
    ".avi",
    ".wmv",
    ".m4v",
    ".flv",
    ".ts",
    ".3gp",
    ".mpg",
}

# Target output formats available for image conversion
IMAGE_TARGET_FORMATS: list[str] = [
    "JPEG",
    "PNG",
    "WEBP",
    "BMP",
    "TIFF",
    "GIF",
    "ICO",
    "PPM",
    "PDF",
]

# Target output formats available for video conversion (without leading dot)
VIDEO_TARGET_FORMATS: list[str] = [
    "mp4",
    "mkv",
    "webm",
    "mov",
    "avi",
    "wmv",
]

# Image formats that cannot be further compressed via PIL (caps, no dot)
UNCOMPRESSIBLE_FORMATS: set[str] = {"BMP", "PPM", "GIF", "ICO", "HEIC", "HEIF"}