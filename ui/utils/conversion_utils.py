import logging
from typing import Dict, List, Tuple

from ui.i18n import t

# Setup module logger
logger = logging.getLogger(__name__)

# Supported target formats for image conversion operations
SUPPORTED_CONVERSION_FORMATS: List[str] = [
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

# Internal mapping of translation keys to hexadecimal color strings
COLOR_HEX_MAP: Dict[str, str] = {
    "color_white": "#FFFFFF",
    "color_black": "#000000",
    "color_light_gray": "#D3D3D3",
    "color_dark_gray": "#808080",
    "color_red": "#FF0000",
    "color_green": "#008000",
    "color_blue": "#0000FF",
    "color_yellow": "#FFFF00",
}


def get_color_options() -> List[Tuple[str, str]]:
    """Returns a list of tuples containing translation keys and localized display names."""
    return [(key, t(key)) for key in COLOR_HEX_MAP.keys()]


def resolve_color_key_to_hex(color_key: str, default: str = "#FFFFFF") -> str:
    """Resolves an i18n color translation key to its corresponding hexadecimal string."""
    return COLOR_HEX_MAP.get(color_key, default)


def normalize_hex_color(raw_color: str, default: str = "#FFFFFF") -> str:
    """Validates and normalizes raw hexadecimal color strings for transparency processing."""
    if not raw_color:
        return default

    clean = raw_color.strip().upper()
    if not clean.startswith("#"):
        clean = f"#{clean}"

    if len(clean) == 7 and all(c in "0123456789ABCDEF" for c in clean[1:]):
        return clean

    logger.warning(
        f"Invalid hexadecimal color '{raw_color}' received. Falling back to default '{default}'."
    )
    return default