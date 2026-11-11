"""Smoke testing utility for verifying runtime dependencies and bundled native binaries."""

import io
import logging
import sys

from PIL import Image

# Setup module logger
logger = logging.getLogger(__name__)


def run_smoke_check() -> bool:
    """Exercises heavy system dependencies and bundled binaries to ensure runtime integrity.

    Checks critical library imports (flet, PIL, pillow_heif, yaml), verifies the bundled
    FFmpeg binary execution along with libx265 encoder availability, and performs an
    in-memory image conversion (PNG to WEBP/JPEG) to validate libheif/native bindings.

    Returns:
        bool: True if all dependency and media conversion checks succeed, False otherwise.
    """
    try:
        # 1. Verify heavy Python dependencies import cleanly
        import flet  # noqa: F401
        import pillow_heif
        import yaml  # noqa: F401

        # Register HEIF opener if available
        if hasattr(pillow_heif, "register_heif_opener"):
            pillow_heif.register_heif_opener()

        # 2. Verify bundled FFmpeg binary execution and libx265 encoder support
        from src.video.utils import ffmpeg_utils
        from src.video.utils.binary_manager import get_ffmpeg_path

        ffmpeg_bin = get_ffmpeg_path()
        if not ffmpeg_bin.exists():
            sys.stderr.write(f"Smoke check failed: FFmpeg binary not found at '{ffmpeg_bin}'.\n")
            return False

        if not ffmpeg_utils.has_encoder(ffmpeg_bin, "libx265"):
            logger.warning("Bundled FFmpeg does not report libx265 encoder availability.")

        # 3. Perform in-memory image conversion (PNG -> WEBP & JPEG)
        img = Image.new("RGBA", (8, 8), color=(255, 0, 0, 128))

        # Convert to WEBP in memory
        webp_buf = io.BytesIO()
        img.save(webp_buf, format="WEBP")
        if webp_buf.getvalue() == b"":
            sys.stderr.write("Smoke check failed: WEBP image encoding generated empty buffer.\n")
            return False

        # Convert to JPEG (requires flattening transparency)
        jpeg_buf = io.BytesIO()
        rgb_img = Image.new("RGB", img.size, (255, 255, 255))
        rgb_img.paste(img, mask=img.getchannel("A"))
        rgb_img.save(jpeg_buf, format="JPEG")
        if jpeg_buf.getvalue() == b"":
            sys.stderr.write("Smoke check failed: JPEG image encoding generated empty buffer.\n")
            return False

        logger.info("Smoke check completed successfully.")
        return True

    except Exception as e:
        sys.stderr.write(f"Smoke check failed with exception: {e}\n")
        logger.error(f"Smoke check execution failure: {e}", exc_info=True)
        return False