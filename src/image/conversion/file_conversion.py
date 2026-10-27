import logging
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, ImageSequence

from src.image.utils.remove_transparency import (
    ALPHA_SUPPORTED_FORMATS,
    NON_ALPHA_FORMATS,
    has_transparency,
    remove_transparency,
)

# Setup module logger
logger = logging.getLogger(__name__)

FORMAT_ALIASES = {"JPG": "JPEG", "JFIF": "JPEG", "TIF": "TIFF"}

# Pixel modes each target format can write. None = no restriction.
ALLOWED_MODES: dict[str, set[str] | None] = {
    "JPEG": {"L", "RGB"},
    "PNG": {"1", "L", "LA", "I;16", "P", "RGB", "RGBA"},
    "WEBP": {"RGB", "RGBA"},
    "BMP": {"1", "L", "P", "RGB"},
    "TIFF": None,
    "GIF": {"L", "P", "RGB"},
    "ICO": {"RGBA"},
    "PPM": {"1", "L", "RGB"},
    "PDF": {"1", "L", "P", "RGB", "CMYK"},
}

# 16/32-bit integer modes that must be scaled (not clipped) to reach 8 bits.
HIGH_DEPTH_MODES = {"I", "I;16", "I;16L", "I;16B", "I;16N"}

# Multi-frame handling: animations and multi-page documents are only kept for
# sensible source -> target pairs.
ANIMATION_SOURCES = {"GIF", "WEBP", "PNG"}
ANIMATION_TARGETS = {"GIF", "WEBP"}
PAGE_TARGETS = {"TIFF", "PDF"}

ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _normalize_format(fmt: str) -> str:
    """Normalizes a format name to the identifier Pillow expects."""
    fmt = fmt.upper().lstrip(".")
    return FORMAT_ALIASES.get(fmt, fmt)


def _to_8bit(frame: Image.Image) -> Image.Image:
    """Scales 16/32-bit images down to 8-bit grayscale instead of clipping."""
    if frame.mode in HIGH_DEPTH_MODES:
        return (
            frame.convert("I").point(lambda p: p * (1 / 256)).convert("L")
        )
    if frame.mode == "F":
        return frame.convert("L")
    return frame


def _square_for_ico(frame: Image.Image) -> Image.Image:
    """Pads to a transparent square and clamps to the 16-256 px ICO range."""
    side = max(frame.size)
    if frame.size != (side, side):
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        canvas.paste(
            frame, ((side - frame.width) // 2, (side - frame.height) // 2)
        )
        frame = canvas
    if side > 256:
        frame = frame.resize((256, 256), Image.Resampling.LANCZOS)
    elif side < 16:
        frame = frame.resize((16, 16), Image.Resampling.LANCZOS)
    return frame


def _prepare_frame(
    frame: Image.Image, fmt: str, background_color: str
) -> Image.Image:
    """Converts a frame into a pixel mode the target format can write."""
    if fmt in NON_ALPHA_FORMATS:
        frame = remove_transparency(frame, background_color)

    # Saving 32-bit "I" images as PNG is deprecated in Pillow; use 16-bit.
    if fmt == "PNG" and frame.mode == "I":
        frame = frame.convert("I;16")

    allowed = ALLOWED_MODES.get(fmt)
    if allowed is not None and frame.mode not in allowed:
        # PNG and TIFF keep 16-bit data; everything else needs 8-bit.
        if fmt not in ("PNG", "TIFF"):
            frame = _to_8bit(frame)
        if frame.mode not in allowed:
            wants_alpha = fmt == "ICO" or (
                fmt in ALPHA_SUPPORTED_FORMATS and has_transparency(frame)
            )
            frame = frame.convert("RGBA" if wants_alpha else "RGB")

    if fmt == "ICO":
        frame = _square_for_ico(frame)
    return frame


def _load_frames(
    img: Image.Image, src_fmt: str, fmt: str
) -> tuple[list[Image.Image], list[int] | None]:
    """Returns the frames to write and per-frame durations (animations only)."""
    n_frames = getattr(img, "n_frames", 1)
    keep_multi = n_frames > 1 and (
        (src_fmt in ANIMATION_SOURCES and fmt in ANIMATION_TARGETS)
        or (src_fmt == "TIFF" and fmt in PAGE_TARGETS)
    )

    if not keep_multi:
        return [ImageOps.exif_transpose(img)], None

    frames: list[Image.Image] = []
    durations: list[int] = []
    for frame in ImageSequence.Iterator(img):
        durations.append(frame.info.get("duration", 100))
        frames.append(frame.copy())
    return frames, durations


def file_converter(
    input_path: Path,
    output_path: Path,
    target_format: str,
    transparency_replacement_color: str = "#FFFFFF",
) -> bool:
    """Converts any supported image file to the specified target format.

    Handles EXIF auto-rotation, transparency flattening for formats without
    alpha, CMYK / 16-bit / palette pixel modes, animated GIF/WEBP/PNG sources,
    multi-page TIFF, square padding and size limits for ICO, and keeps the
    ICC color profile when possible.

    Args:
        input_path (Path): Path to the source image file.
        output_path (Path): Path where the converted image will be saved.
        target_format (str): Desired output format (e.g., 'JPEG', 'PNG', 'WEBP').
        transparency_replacement_color (str, optional): Hex color code used to replace
            the Alpha channel if target format lacks alpha support. Defaults to "#FFFFFF".

    Returns:
        bool: True if conversion succeeded, False otherwise.
    """
    try:
        if input_path.resolve() == output_path.resolve():
            logger.error(
                f"Refusing to convert '{input_path.name}': output path is the source file."
            )
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)
        fmt = _normalize_format(target_format)

        with Image.open(input_path) as img:
            src_fmt = (img.format or "").upper()
            loop = img.info.get("loop", 0)
            icc = (
                img.info.get("icc_profile")
                if img.mode in ("RGB", "RGBA", "P")
                else None
            )

            frames, durations = _load_frames(img, src_fmt, fmt)
            prepared = [
                _prepare_frame(f, fmt, transparency_replacement_color)
                for f in frames
            ]
            multi = len(prepared) > 1
            if multi and fmt == "WEBP":
                prepared = [f.convert("RGBA") for f in prepared]

            save_kwargs: dict[str, Any] = {}
            if fmt == "JPEG":
                save_kwargs["quality"] = 95
            elif fmt == "WEBP":
                save_kwargs["quality"] = 90
            elif fmt == "ICO":
                side = prepared[0].width
                save_kwargs["sizes"] = [
                    (s, s) for s in sorted({*(x for x in ICO_SIZES if x <= side), side})
                ]

            if icc and fmt in ("JPEG", "PNG", "WEBP", "TIFF"):
                save_kwargs["icc_profile"] = icc

            if multi:
                save_kwargs["save_all"] = True
                save_kwargs["append_images"] = prepared[1:]
                if fmt in ANIMATION_TARGETS:
                    save_kwargs["duration"] = durations
                    save_kwargs["loop"] = loop

            prepared[0].save(output_path, format=fmt, **save_kwargs)

        logger.info(
            f"Successfully converted '{input_path.name}' to '{fmt}'."
        )
        return True

    except Exception as e:
        logger.error(
            f"Failed to convert '{input_path.name}': {e}", exc_info=True
        )
        output_path.unlink(missing_ok=True)
        return False
