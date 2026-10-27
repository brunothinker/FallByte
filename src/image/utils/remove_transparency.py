import logging

from PIL import Image

# Setup module logger
logger = logging.getLogger(__name__)

# Formats that natively support full alpha channel transparency (32-bit RGBA)
ALPHA_SUPPORTED_FORMATS = {"PNG", "WEBP", "TIFF", "ICO"}

# Formats known to lack proper alpha channel (transparency) support
NON_ALPHA_FORMATS = {"JPEG", "JPG", "BMP", "PPM", "PDF", "GIF"}

_ALPHA_MODES = {"RGBA", "LA", "PA", "RGBa", "La"}


def has_transparency(image: Image.Image) -> bool:
    """Checks whether an image carries any transparency information.

    Covers alpha-channel modes and images (palette, grayscale or RGB) that
    declare a transparent color/index through the ``transparency`` info key.
    """
    return image.mode in _ALPHA_MODES or "transparency" in image.info


def remove_transparency(
    image: Image.Image, background_color: str = "#FFFFFF"
) -> Image.Image:
    """Replaces alpha transparency in an image with a solid background color.

    Args:
        image (Image.Image): Source PIL Image object.
        background_color (str, optional): Hex color code used to replace
            the alpha channel. Defaults to "#FFFFFF" (White).

    Returns:
        Image.Image: A new RGB image with transparency flattened over the
            chosen background color, or the original image unchanged if it
            has no transparency.
    """
    if not has_transparency(image):
        return image

    try:
        rgba_image = image.convert("RGBA")
        background = Image.new("RGB", image.size, background_color)
        background.paste(rgba_image, mask=rgba_image.getchannel("A"))
        logger.debug(
            f"Successfully replaced transparency with background color '{background_color}'."
        )
        return background

    except (ValueError, OSError) as e:
        logger.error(
            f"Failed to remove transparency from image: {e}", exc_info=True
        )
        # Fallback to standard RGB conversion if pasting fails
        return image.convert("RGB")
