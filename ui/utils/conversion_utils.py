import logging

from src.formats import (
    IMAGE_TARGET_FORMATS as SUPPORTED_CONVERSION_FORMATS,
)
from ui.i18n import t

# Setup module logger
logger = logging.getLogger(__name__)

# Expose supported conversion formats for UI consumption
__all__ = [
    "COLOR_HEX_MAP",
    "SUPPORTED_CONVERSION_FORMATS",
    "get_color_options",
    "normalize_hex_color",
    "resolve_color_key_to_hex",
]

# Internal mapping of translation keys to hexadecimal color strings
COLOR_HEX_MAP: dict[str, str] = {
    "color_white": "#FFFFFF",
    "color_black": "#000000",
    "color_light_gray": "#D3D3D3",
    "color_dark_gray": "#808080",
    "color_red": "#FF0000",
    "color_green": "#008000",
    "color_blue": "#0000FF",
    "color_yellow": "#FFFF00",
}


def get_color_options() -> list[tuple[str, str]]:
    """Returns a list of tuples containing translation keys and localized display names.

    Returns:
        list[tuple[str, str]]: List of (color_key, localized_name) tuples.
    """
    return [(key, t(key)) for key in COLOR_HEX_MAP]


def resolve_color_key_to_hex(color_key: str, default: str = "#FFFFFF") -> str:
    """Resolves an i18n color translation key to its corresponding hexadecimal string.

    Args:
        color_key (str): Translation key representing the color (e.g. 'color_white').
        default (str, optional): Default hex color fallback. Defaults to "#FFFFFF".

    Returns:
        str: Validated hexadecimal color string.
    """
    return COLOR_HEX_MAP.get(color_key, default)


def normalize_hex_color(raw_color: str, default: str = "#FFFFFF") -> str:
    """Validates and normalizes raw hexadecimal color strings for transparency processing.

    Args:
        raw_color (str): Input hexadecimal color string to validate.
        default (str, optional): Fallback hex color if validation fails. Defaults to "#FFFFFF".

    Returns:
        str: Normalized upper-case 7-character hex color string (e.g. "#FFFFFF").
    """
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