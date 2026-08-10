import logging
from pathlib import Path
from PIL import Image, ImageOps

from src.image.utils.remove_transparency import NON_ALPHA_FORMATS

logger = logging.getLogger(__name__)


def file_compressor(
        input_path: Path,
        output_path: Path,
        quality: int = 80
) -> bool:
    """
    Compresses a single image file while strictly maintaining its ORIGINAL format.
    Fails explicitly if the image contains transparency but the target format doesn't support it.
    Uses PNG color quantization (TinyPNG style) when quality < 90.
    """
    try:
        quality = max(1, min(100, quality))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with Image.open(input_path) as img:
            fmt = (img.format or input_path.suffix.lstrip(".")).upper()
            if fmt == "JPG":
                fmt = "JPEG"

            has_alpha = (
                    img.mode in ("RGBA", "LA") or
                    (img.mode == "P" and "transparency" in img.info)
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
            save_kwargs = {"optimize": True}

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
                                method=Image.Quantize.FASTOCTREE
                            )
                        else:
                            final_img = final_img.convert("RGB").quantize(
                                colors=max_colors,
                                method=Image.Quantize.MEDIANCUT
                            )
                    except Exception as quant_err:
                        logger.warning(f"Quantization skipped for '{input_path.name}': {quant_err}")

            elif fmt == "TIFF":
                save_kwargs["compression"] = "tiff_deflate"

            if fmt == "ICO" and (final_img.width > 256 or final_img.height > 256):
                final_img = final_img.copy()
                final_img.thumbnail((256, 256), Image.Resampling.LANCZOS)

            final_img.save(output_path, format=fmt, **save_kwargs)

            logger.info(
                f"Successfully compressed '{input_path.name}' "
                f"[Format: {fmt} | Quality: {quality}%]."
            )
            return True

    except Exception as e:
        logger.error(f"Failed to compress '{input_path.name}': {e}", exc_info=True)
        return False