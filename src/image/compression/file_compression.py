import logging
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from src.image.utils.remove_transparency import NON_ALPHA_FORMATS

# Setup module logger
logger = logging.getLogger(__name__)


def file_compressor(
    input_path: Path, output_path: Path, quality: int = 80
) -> bool:
    """Compresses a single image file while strictly maintaining its original format.

    Uses format-specific optimizations such as quality levels for JPEG/WEBP,
    pngquant-style color palette quantization for PNG (when quality < 90),
    tiff_deflate compression for TIFF, and auto-rotation from EXIF metadata.
    Refuses execution if the file contains alpha transparency but target format
    lacks alpha support.

    Args:
        input_path (Path): Path to the source image file.
        output_path (Path): Destination path where compressed image will be written.
        quality (int, optional): Compression quality percentage (1-100). Defaults to 80.

    Returns:
        bool: True if compression succeeded, False otherwise.
    """
    try:
        quality = max(1, min(100, quality))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with Image.open(input_path) as img:
            fmt = (img.format or input_path.suffix.lstrip(".")).upper()
            if fmt == "JPG":
                fmt = "JPEG"

            has_alpha = img.mode in ("RGBA", "LA") or (
                img.mode == "P" and "transparency" in img.info
            )

            # Refuse to compress if alpha channel exists but format lacks support
            if has_alpha and fmt in NON_ALPHA_FORMATS:
                logger.warning(
                    f"Compression skipped for '{input_path.name}': "
                    f"Format '{fmt}' does not support transparency. "
                    f"Please use Converter module first."
                )
                return False

            final_img = ImageOps.exif_transpose(img)
            save_kwargs: dict[str, Any] = {"optimize": True}

            if fmt in ("JPEG", "WEBP"):
                save_kwargs["quality"] = quality

            elif fmt == "PNG":
                save_kwargs["compress_level"] = 9

                # Color quantization for PNG (TinyPNG style)
                if quality < 90:
                    max_colors = max(32, int((quality / 100) * 256))
                    try:
                        if has_alpha:
                            final_img = final_img.quantize(
                                colors=max_colors,
                                method=Image.Quantize.FASTOCTREE,
                            )
                        else:
                            final_img = final_img.convert("RGB").quantize(
                                colors=max_colors,
                                method=Image.Quantize.MEDIANCUT,
                            )
                    except (ValueError, OSError) as quant_err:
                        logger.warning(
                            f"Quantization skipped for '{input_path.name}': {quant_err}"
                        )

            elif fmt == "TIFF":
                save_kwargs["compression"] = "tiff_deflate"

            if fmt == "ICO" and (
                final_img.width > 256 or final_img.height > 256
            ):
                final_img = final_img.copy()
                final_img.thumbnail((256, 256), Image.Resampling.LANCZOS)

            final_img.save(output_path, format=fmt, **save_kwargs)

            logger.info(
                f"Successfully compressed '{input_path.name}' "
                f"[Format: {fmt} | Quality: {quality}%]."
            )
            return True

    except (ValueError, OSError) as e:
        logger.error(
            f"Failed to compress '{input_path.name}': {e}", exc_info=True
        )
        return False