SUPPORTED_CONVERSION_FORMATS = [
    "JPEG",
    "PNG",
    "WEBP",
    "BMP",
    "TIFF",
    "GIF",
    "ICO",
    "PPM",
    "PDF"
]


def normalize_hex_color(raw_color: str, default: str = "#FFFFFF") -> str:
    """Validates and normalizes Hexadecimal color string for transparency handling."""
    if not raw_color:
        return default
    clean = raw_color.strip().upper()
    if not clean.startswith("#"):
        clean = f"#{clean}"
    if len(clean) == 7 and all(c in "0123456789ABCDEF" for c in clean[1:]):
        return clean
    return default