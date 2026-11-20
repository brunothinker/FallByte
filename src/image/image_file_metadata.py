import logging
import math
import os
import tempfile
from pathlib import Path
from typing import Any

import pillow_heif
from PIL import Image, ImageOps, ImageSequence

# Register HEIC/HEIF opener at startup for Pillow integration
if hasattr(pillow_heif, "register_heif_opener"):
    pillow_heif.register_heif_opener()

logger = logging.getLogger(__name__)

FORMAT_ALIASES = {
    "JPG": "JPEG",
    "MPO": "JPEG",
    "JFIF": "JPEG",
    "TIF": "TIFF",
    "HEIC": "HEIF",
}

# Formats that Pillow cannot natively encode without custom container encoders
UNWRITABLE_METADATA_FORMATS: frozenset[str] = frozenset({"HEIC", "HEIF"})


def _normalize_format(raw_format: str | None, path: Path) -> str:
    """Resolves the canonical Pillow image format identifier from metadata or extension."""
    fmt = (raw_format or path.suffix.lstrip(".")).upper()
    return FORMAT_ALIASES.get(fmt, fmt)


def _strip_frame_pixels(frame: Image.Image) -> Image.Image:
    """Copies raw pixel data into a clean Image instance without info/metadata dictionaries."""
    clean = frame.copy()
    clean.info.clear()
    return clean


def file_metadata_remover(input_path: Path, output_path: Path) -> bool:
    """Strips EXIF, GPS, XMP, ICC, and embedded text/camera metadata from an image file.

    Applies EXIF orientation (`ImageOps.exif_transpose`) prior to removing tags so
    rotated photographs preserve their intended display orientation. Multi-frame
    animations (GIF, WEBP, TIFF) preserve frame timing and loop counts while
    stripping metadata chunks. HEIC/HEIF inputs are decoded and saved as clean PNGs.

    Writes output atomically via temporary file + `os.replace`.

    Args:
        input_path (Path): Path to the source image file.
        output_path (Path): Destination path where the sanitized image will be written.

    Returns:
        bool: True if metadata removal succeeded, False otherwise.
    """
    tmp_path: Path | None = None
    try:
        if not input_path.exists() or input_path.stat().st_size == 0:
            logger.error(
                f"Refusing to strip metadata from '{input_path.name}': file does not exist or is empty."
            )
            return False

        if input_path.resolve() == output_path.resolve():
            logger.error(
                f"Refusing to strip metadata from '{input_path.name}': output path is the source file."
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
            save_fmt = "PNG" if fmt in UNWRITABLE_METADATA_FORMATS else fmt
            n_frames = getattr(img, "n_frames", 1)
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
        return True

    except Exception:
        logger.exception(f"Failed to remove metadata from '{input_path.name}'")
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return False
