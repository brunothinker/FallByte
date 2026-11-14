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

# Supported input audio extensions (lowercase with leading dot)
SUPPORTED_AUDIO_EXTENSIONS: set[str] = {
    ".mp3",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".flac",
    ".wav",
    ".wma",
    ".aiff",
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

# Target output formats available for audio conversion (without leading dot)
AUDIO_TARGET_FORMATS: list[str] = [
    "mp3",
    "m4a",
    "opus",
    "ogg",
    "flac",
    "wav",
]

# Image formats that cannot be further compressed via PIL (caps, no dot)
UNCOMPRESSIBLE_FORMATS: set[str] = {"BMP", "PPM", "GIF", "ICO", "HEIC", "HEIF"}

# Audio formats that are not re-encoded during compression (caps, no dot)
UNCOMPRESSIBLE_AUDIO_FORMATS: set[str] = {"FLAC", "WAV", "AAC", "WMA", "AIFF"}