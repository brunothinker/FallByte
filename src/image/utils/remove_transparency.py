import logging
from PIL import Image

# Setup module logger
logger = logging.getLogger(__name__)

# Formats that natively support full alpha channel transparency (32-bit RGBA)
ALPHA_SUPPORTED_FORMATS = {"PNG", "WEBP", "TIFF", "ICO"}

# Formats known to lack proper alpha channel (transparency) support
NON_ALPHA_FORMATS = {"JPEG", "JPG", "BMP", "PPO", "PPM", "PDF", "GIF"}


def remove_transparency(
        image: Image.Image,
        background_color: str = "#FFFFFF"
) -> Image.Image:
    """
    Replaces alpha transparency in an image with a solid background color.

    Args:
        image (Image.Image): Source PIL Image object.
        background_color (str, optional): Hex color code used to replace
            the alpha channel. Defaults to "#FFFFFF" (White).

    Returns:
        Image.Image: A new RGB PIL Image with transparency flattened over
            the chosen background color. Returns original image if no alpha channel exists.
    """
    # Check if image actually has an alpha channel or palette with transparency
    if image.mode in ("RGBA", "LA", "P"):
        try:
            # Create a solid color background image matching source dimensions
            background = Image.new("RGB", image.size, background_color)

            # Ensure image is in RGBA mode to safely extract the alpha channel mask
            rgba_image = image.convert("RGBA")
            alpha_mask = rgba_image.split()[3]

            # Paste source image onto background using the alpha mask
            background.paste(rgba_image, mask=alpha_mask)

            logger.debug(f"Successfully replaced transparency with background color '{background_color}'.")
            return background

        except Exception as e:
            logger.error(f"Failed to remove transparency from image: {e}", exc_info=True)
            # Fallback to standard RGB conversion if pasting fails
            return image.convert("RGB")

    return image