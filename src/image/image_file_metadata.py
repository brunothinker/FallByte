import logging
import math
import os
import tempfile
from pathlib import Path
from typing import Any

import pillow_heif
from PIL import Image, ImageOps, ImageSequence

from src.formats import UNWRITABLE_IMAGE_FORMATS, normalize_image_format
from src.image.utils.image_limits import (
    configure_image_pixel_limits,
    log_decompression_bomb_error,
)
from src.image.utils.image_metadata_utils import clear_metadata_keep_transparency
from src.image.utils.jpeg_lossless_metadata import strip_jpeg_metadata_bytes
from src.utils.file_result import FileResult

# Register HEIC/HEIF opener at startup for Pillow integration
if hasattr(pillow_heif, "register_heif_opener"):
    pillow_heif.register_heif_opener()

configure_image_pixel_limits()

logger = logging.getLogger(__name__)

UNWRITABLE_METADATA_FORMATS = UNWRITABLE_IMAGE_FORMATS


def _strip_frame_pixels(frame: Image.Image) -> Image.Image:
    """Copies raw pixel data into a clean Image instance without metadata.

    Every ``info`` entry is dropped except ``transparency``, which is required
    to render palette/grayscale/RGB images with a transparent color correctly.
    """
    return clear_metadata_keep_transparency(frame.copy())


def file_metadata_remover(input_path: Path, output_path: Path) -> FileResult:
    """Strips EXIF, GPS, XMP, ICC, and embedded text/camera metadata from an image file.

    Uses a hybrid lossless path for unrotated JPEGs (EXIF Orientation absent or 1):
    APPn/COM metadata markers (EXIF, GPS, XMP, ICC, IPTC, COM) are stripped directly
    from the JPEG bitstream without decoding or re-encoding DCT coefficients.
    Rotated JPEGs (EXIF Orientation 2..8) fall back to `ImageOps.exif_transpose`
    plus re-encoding so display orientation is baked into the pixels. Multi-frame
    animations (GIF, WEBP, TIFF) preserve frame timing and loop counts while
    stripping metadata chunks. HEIC/HEIF inputs are decoded and saved as clean PNGs.

    Writes output atomically via temporary file + `os.replace`.

    Args:
        input_path (Path): Path to the source image file.
        output_path (Path): Destination path where the sanitized image will be written.

    Returns:
        FileResult: Outcome of the metadata removal operation.
    """
    tmp_path: Path | None = None
    try:
        if not input_path.exists() or input_path.stat().st_size == 0:
            logger.error(
                f"Refusing to strip metadata from '{input_path.name}': file does not exist or is empty."
            )
            return FileResult.failed()

        if input_path.resolve() == output_path.resolve():
            logger.error(
                f"Refusing to strip metadata from '{input_path.name}': output path is the source file."
            )
            return FileResult.failed()

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            dir=output_path.parent,
            prefix=f".{output_path.stem}_tmp_",
            suffix=output_path.suffix,
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)

        with Image.open(input_path) as img:
            fmt = normalize_image_format(img.format, input_path)
            save_fmt = "PNG" if fmt in UNWRITABLE_METADATA_FORMATS else fmt
            n_frames = getattr(img, "n_frames", 1)
            orientation = img.getexif().get(274)

            if fmt == "JPEG" and n_frames == 1 and orientation in (None, 1):
                raw_jpeg = input_path.read_bytes()
                cleaned_jpeg = strip_jpeg_metadata_bytes(raw_jpeg)
                tmp_path.write_bytes(cleaned_jpeg)
                os.replace(tmp_path, output_path)
                logger.info(
                    f"Successfully stripped metadata losslessly from '{input_path.name}' [Format: JPEG]."
                )
                return FileResult.processed()

            save_kwargs: dict[str, Any] = {}

            multi = n_frames > 1 and save_fmt in ("GIF", "WEBP", "TIFF")

            if multi:
                raw_frames = [f.copy() for f in ImageSequence.Iterator(img)]
                clean_frames = [_strip_frame_pixels(f) for f in raw_frames]
                if save_fmt in ("GIF", "WEBP"):
                    save_kwargs["duration"] = [
                        f.info.get("duration", 100) for f in raw_frames
                    ]
                    save_kwargs["loop"] = img.info.get("loop", 0)
                if save_fmt == "WEBP":
                    clean_frames = [f.convert("RGBA") for f in clean_frames]
                final_img = clean_frames[0]
                save_kwargs["save_all"] = True
                save_kwargs["append_images"] = clean_frames[1:]
            else:
                transposed = ImageOps.exif_transpose(img)
                final_img = _strip_frame_pixels(transposed)

            if save_fmt == "JPEG":
                if final_img.mode not in ("L", "RGB"):
                    final_img = final_img.convert("RGB")
                save_kwargs.update(quality=95, subsampling=0, optimize=True)
            elif save_fmt == "WEBP":
                save_kwargs["quality"] = 95
            elif save_fmt == "PNG":
                save_kwargs["optimize"] = True
            elif save_fmt == "TIFF":
                save_kwargs["compression"] = "tiff_deflate"
            elif save_fmt == "ICO":
                side = min(
                    256, max(16, int(math.sqrt(final_img.width * final_img.height)))
                )
                final_img = final_img.convert("RGBA").resize(
                    (side, side), Image.Resampling.LANCZOS
                )
                save_kwargs["sizes"] = [(side, side)]

            final_img.save(tmp_path, format=save_fmt, **save_kwargs)

        os.replace(tmp_path, output_path)

        logger.info(
            f"Successfully removed metadata from '{input_path.name}' [Format: {save_fmt}]."
        )
        return FileResult.processed()

    except Image.DecompressionBombError as bomb_err:
        log_decompression_bomb_error(logger, input_path.name, bomb_err)
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return FileResult.failed()
    except Exception:
        logger.exception(f"Failed to remove metadata from '{input_path.name}'")
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return FileResult.failed()
