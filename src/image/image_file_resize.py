import logging
import math
import os
import tempfile
from pathlib import Path
from typing import Any

import pillow_heif
from PIL import Image, ImageOps, ImageSequence

from src.formats import UNWRITABLE_IMAGE_FORMATS, normalize_image_format
from src.utils.file_result import FileResult

# Register HEIC/HEIF opener at startup for Pillow integration
if hasattr(pillow_heif, "register_heif_opener"):
    pillow_heif.register_heif_opener()

logger = logging.getLogger(__name__)

UNRESIZABLE_FORMATS = UNWRITABLE_IMAGE_FORMATS


def compute_target_dimensions(
    width: int,
    height: int,
    mode: str,
    max_width: int | None = None,
    max_height: int | None = None,
    percentage: int | None = None,
) -> tuple[int, int]:
    """Computes target (width, height) preserving aspect ratio without upscaling.

    Args:
        width (int): Source image width in pixels.
        height (int): Source image height in pixels.
        mode (str): Resizing mode ('dimension' or 'percentage').
        max_width (int | None, optional): Maximum target width in pixels.
        max_height (int | None, optional): Maximum target height in pixels.
        percentage (int | None, optional): Scale percentage (1-100).

    Returns:
        tuple[int, int]: Computed (target_width, target_height) with minimum 1x1 px,
            never exceeding source dimensions.

    Raises:
        ValueError: If mode or target dimensions/percentage are invalid.
    """
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid source image dimensions: {width}x{height}")

    normalized_mode = mode.strip().lower()

    if normalized_mode == "percentage":
        if percentage is None or percentage <= 0:
            raise ValueError(f"Invalid resize percentage: {percentage}")
        scale = percentage / 100.0
        if scale >= 1.0:
            return width, height
    elif normalized_mode == "dimension":
        scale_candidates: list[float] = []
        if max_width is not None and max_width > 0:
            scale_candidates.append(max_width / width)
        if max_height is not None and max_height > 0:
            scale_candidates.append(max_height / height)

        if not scale_candidates:
            raise ValueError(
                "At least one positive target dimension (max_width or max_height) is required."
            )

        scale = min(scale_candidates)
        if scale >= 1.0:
            return width, height
    else:
        raise ValueError(f"Unsupported resize mode: '{mode}'")

    target_w = min(width, max(1, round(width * scale)))
    target_h = min(height, max(1, round(height * scale)))
    return target_w, target_h


def _resize_frame(frame: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    """Resizes a single frame using high-quality Lanczos resampling."""
    if frame.size == target_size:
        return frame.copy()

    # Palette ('P') or 1-bit ('1') frames cannot use Lanczos directly in Pillow
    if frame.mode in ("P", "1"):
        has_alpha = "transparency" in frame.info
        converted = frame.convert("RGBA" if has_alpha else "RGB")
        return converted.resize(target_size, Image.Resampling.LANCZOS)

    return frame.resize(target_size, Image.Resampling.LANCZOS)


def file_resizer(
    input_path: Path,
    output_path: Path,
    mode: str = "dimension",
    max_width: int | None = 1920,
    max_height: int | None = 1080,
    percentage: int | None = 50,
) -> FileResult:
    """Resizes a single image file while preserving aspect ratio and original format.

    Applies EXIF orientation before computing target dimensions, never upscales
    images smaller than the target, uses `Image.Resampling.LANCZOS`, preserves
    ICC color profiles and EXIF metadata where supported, and writes output
    atomically via temporary file + `os.replace`.

    Args:
        input_path (Path): Path to the source image file.
        output_path (Path): Destination path where the resized image will be saved.
        mode (str, optional): Resizing strategy ('dimension' or 'percentage').
            Defaults to 'dimension'.
        max_width (int | None, optional): Maximum target width in pixels for 'dimension' mode.
            Defaults to 1920.
        max_height (int | None, optional): Maximum target height in pixels for 'dimension' mode.
            Defaults to 1080.
        percentage (int | None, optional): Target scale percentage for 'percentage' mode.
            Defaults to 50.

    Returns:
        FileResult: Outcome of the resize operation.
    """
    tmp_path: Path | None = None
    try:
        if not input_path.exists() or input_path.stat().st_size == 0:
            logger.error(
                f"Refusing to resize '{input_path.name}': file does not exist or is empty."
            )
            return FileResult.failed()

        if input_path.resolve() == output_path.resolve():
            logger.error(
                f"Refusing to resize '{input_path.name}': output path is the source file."
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
            save_fmt = "PNG" if fmt in UNRESIZABLE_FORMATS else fmt
            n_frames = getattr(img, "n_frames", 1)
            icc = img.info.get("icc_profile")
            save_kwargs: dict[str, Any] = {}

            multi = n_frames > 1 and save_fmt in ("GIF", "WEBP", "TIFF")

            if multi:
                raw_frames = [f.copy() for f in ImageSequence.Iterator(img)]
                target_size = compute_target_dimensions(
                    width=raw_frames[0].width,
                    height=raw_frames[0].height,
                    mode=mode,
                    max_width=max_width,
                    max_height=max_height,
                    percentage=percentage,
                )
                resized_frames = [_resize_frame(f, target_size) for f in raw_frames]
                if save_fmt in ("GIF", "WEBP"):
                    save_kwargs["duration"] = [
                        f.info.get("duration", 100) for f in raw_frames
                    ]
                    save_kwargs["loop"] = img.info.get("loop", 0)
                if save_fmt == "WEBP":
                    resized_frames = [f.convert("RGBA") for f in resized_frames]
                final_img = resized_frames[0]
                save_kwargs["save_all"] = True
                save_kwargs["append_images"] = resized_frames[1:]
            else:
                transposed = ImageOps.exif_transpose(img)
                target_size = compute_target_dimensions(
                    width=transposed.width,
                    height=transposed.height,
                    mode=mode,
                    max_width=max_width,
                    max_height=max_height,
                    percentage=percentage,
                )
                final_img = _resize_frame(transposed, target_size)

            exif = final_img.info.get("exif")

            if save_fmt == "JPEG":
                if final_img.mode not in ("L", "RGB"):
                    final_img = final_img.convert("RGB")
                save_kwargs.update(quality=92, optimize=True)
                if exif:
                    save_kwargs["exif"] = exif
            elif save_fmt == "WEBP":
                save_kwargs["quality"] = 90
                if exif:
                    save_kwargs["exif"] = exif
            elif save_fmt == "PNG":
                save_kwargs["optimize"] = True
            elif save_fmt == "TIFF":
                save_kwargs["compression"] = "tiff_deflate"
            elif save_fmt == "ICO":
                side = min(256, max(16, int(math.sqrt(target_size[0] * target_size[1]))))
                final_img = final_img.convert("RGBA").resize(
                    (side, side), Image.Resampling.LANCZOS
                )
                save_kwargs["sizes"] = [(side, side)]

            if icc and save_fmt in ("JPEG", "PNG", "WEBP", "TIFF"):
                save_kwargs["icc_profile"] = icc

            final_img.save(tmp_path, format=save_fmt, **save_kwargs)

        os.replace(tmp_path, output_path)

        logger.info(
            f"Successfully resized '{input_path.name}' to {target_size[0]}x{target_size[1]}."
        )
        return FileResult.processed()

    except Exception:
        logger.exception(f"Failed to resize '{input_path.name}'")
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return FileResult.failed()
