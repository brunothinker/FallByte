import logging
from pathlib import Path
from PIL import Image, ImageOps

from src.image.utils.remove_transparency import remove_transparency, NON_ALPHA_FORMATS

# Setup module logger
logger = logging.getLogger(__name__)


def file_converter(
        input_path: Path,
        output_path: Path,
        target_format: str,
        transparency_replacement_color: str = "#FFFFFF"
) -> bool:
    """
    Converts any supported image file to the specified target format.

    Args:
        input_path (Path): Path to the source image file.
        output_path (Path): Path where the converted image will be saved.
        target_format (str): Desired output format (e.g., 'JPEG', 'PNG', 'WEBP').
        transparency_replacement_color (str, optional): Hex color code used to replace
            the Alpha channel if the target format does not support transparency.
            Defaults to "#FFFFFF".

    Returns:
        bool: True if conversion succeeded, False otherwise.
    """
    try:
        # Ensure the destination directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with Image.open(input_path) as img:
            # Auto-rotate image based on EXIF orientation tags
            img = ImageOps.exif_transpose(img)

            # Normalize target format extension
            fmt = target_format.upper()
            if fmt == "JPG":
                fmt = "JPEG"

            # Handle transparency fallback if target format lacks alpha support
            if fmt in NON_ALPHA_FORMATS:
                final_img = remove_transparency(
                    image=img,
                    background_color=transparency_replacement_color
                )
            else:
                final_img = img

            # Defensive check: ICO format enforces a maximum dimension of 256x256
            if fmt == "ICO" and (final_img.width > 256 or final_img.height > 256):
                final_img = final_img.copy()
                final_img.thumbnail((256, 256), Image.Resampling.LANCZOS)

            # Save converted file
            final_img.save(output_path, format=fmt)
            logger.info(f"Successfully converted '{input_path.name}' to '{fmt}'.")
            return True

    except Exception as e:
        logger.error(f"Failed to convert '{input_path.name}': {e}", exc_info=True)
        return False