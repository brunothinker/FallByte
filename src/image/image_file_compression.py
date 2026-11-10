import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import pillow_heif
from PIL import Image, ImageOps, ImageSequence

from src.formats import UNCOMPRESSIBLE_FORMATS
from src.image.utils.remove_transparency import has_transparency
from src.utils.cleanup import copy_original_file_atomically

# Register HEIC/HEIF opener at startup for Pillow integration
if hasattr(pillow_heif, "register_heif_opener"):
    pillow_heif.register_heif_opener()

# Setup module logger
logger = logging.getLogger(__name__)

FORMAT_ALIASES = {
    "JPG": "JPEG",
    "MPO": "JPEG",
    "JFIF": "JPEG",
    "TIF": "TIFF",
    "HEIC": "HEIF",
}

# Formats whose compression is skipped (original file is kept as-is):
# BMP/PPM are raw, GIF/ICO cannot be safely re-encoded without losing
# animation frames or embedded icon sizes. HEIC/HEIF compression as output is
# skipped to prevent generation of degraded native containers without pillow-heif encoder support.


def _normalize_format(raw_format: str | None, path: Path) -> str:
    """Resolves the real image format, mapping aliases (JPG/MPO -> JPEG)."""
    fmt = (raw_format or path.suffix.lstrip(".")).upper()
    return FORMAT_ALIASES.get(fmt, fmt)


def _quantize_png(img: Image.Image, quality: int) -> Image.Image:
    """Reduces a PNG's palette (TinyPNG style). Returns the input if unsupported."""
    if img.mode not in ("RGB", "RGBA", "P"):
        # L / LA / 16-bit grayscale are left untouched to avoid damaging them.
        return img

    max_colors = max(32, int((quality / 100) * 256))
    try:
        if has_transparency(img):
            return img.convert("RGBA").quantize(
                colors=max_colors, method=Image.Quantize.FASTOCTREE
            )
        return img.convert("RGB").quantize(
            colors=max_colors, method=Image.Quantize.MEDIANCUT
        )
    except (ValueError, OSError) as quant_err:
        logger.warning(f"Quantization skipped: {quant_err}")
        return img


def file_compressor(
    input_path: Path, output_path: Path, quality: int = 80
) -> bool:
    """Compresses a single image file while strictly maintaining its original format.

    Uses format-specific optimizations: quality levels for JPEG/WEBP,
    pngquant-style palette quantization for PNG (when quality < 90),
    deflate for TIFF. EXIF orientation is applied; ICC profile and EXIF
    metadata are preserved where the format allows.

    Writes output atomically to a temporary file before moving it into place via
    os.replace to ensure pre-existing files are never corrupted upon failure.

    Formats that cannot be re-encoded safely (BMP, PPM, GIF, ICO, HEIC, HEIF)
    and animated PNGs are copied unchanged. If the compressed result is not smaller
    than the original, the original file is kept as the output.

    Args:
        input_path (Path): Path to the source image file.
        output_path (Path): Destination path where compressed image will be written.
        quality (int, optional): Compression quality percentage (1-100). Defaults to 80.

    Returns:
        bool: True if compression succeeded, False otherwise.
    """
    tmp_path = None
    try:
        quality = max(1, min(100, int(quality)))

        if input_path.resolve() == output_path.resolve():
            logger.error(
                f"Refusing to compress '{input_path.name}': output path is the source file."
            )
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            dir=output_path.parent,
            prefix=f".{output_path.stem}_tmp_",
            suffix=output_path.suffix,
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)

        with Image.open(input_path) as img:
            fmt = _normalize_format(img.format, input_path)
            n_frames = getattr(img, "n_frames", 1)

            if fmt in UNCOMPRESSIBLE_FORMATS:
                tmp_path.unlink(missing_ok=True)
                return copy_original_file_atomically(
                    input_path, output_path, f"{fmt} cannot be compressed safely"
                )
            if fmt == "PNG" and n_frames > 1:
                tmp_path.unlink(missing_ok=True)
                return copy_original_file_atomically(
                    input_path, output_path, "animated PNG would lose its frames"
                )

            icc = img.info.get("icc_profile")
            save_kwargs: dict[str, Any] = {}
            multi = n_frames > 1 and fmt in ("WEBP", "TIFF")

            if multi:
                frames = [f.copy() for f in ImageSequence.Iterator(img)]
                if fmt == "WEBP":
                    save_kwargs["duration"] = [
                        f.info.get("duration", 100) for f in frames
                    ]
                    save_kwargs["loop"] = img.info.get("loop", 0)
                    frames = [f.convert("RGBA") for f in frames]
                final_img = frames[0]
                save_kwargs["save_all"] = True
                save_kwargs["append_images"] = frames[1:]
            else:
                final_img = ImageOps.exif_transpose(img)

            exif = final_img.info.get("exif")

            if fmt == "JPEG":
                save_kwargs.update(
                    quality=quality, optimize=True, progressive=True
                )
                if exif:
                    save_kwargs["exif"] = exif
            elif fmt == "WEBP":
                save_kwargs["quality"] = quality
                if exif:
                    save_kwargs["exif"] = exif
            elif fmt == "PNG":
                save_kwargs.update(optimize=True, compress_level=9)
                if quality < 90:
                    final_img = _quantize_png(final_img, quality)
            elif fmt == "TIFF":
                save_kwargs["compression"] = "tiff_deflate"

            if icc and fmt in ("JPEG", "PNG", "WEBP", "TIFF"):
                save_kwargs["icc_profile"] = icc

            final_img.save(tmp_path, format=fmt, **save_kwargs)

        original_size = input_path.stat().st_size
        if tmp_path.stat().st_size >= original_size:
            tmp_path.unlink(missing_ok=True)
            return copy_original_file_atomically(
                input_path,
                output_path,
                f"compressed result was not smaller at {quality}% quality",
            )

        os.replace(tmp_path, output_path)

        logger.info(
            f"Successfully compressed '{input_path.name}' "
            f"[Format: {fmt} | Quality: {quality}%]."
        )
        return True

    except Exception:
        logger.exception(f"Failed to compress '{input_path.name}'")
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return False