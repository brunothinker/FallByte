import logging

from PIL import Image

logger = logging.getLogger(__name__)


def clear_metadata_keep_transparency(image: Image.Image) -> Image.Image:
    """Clears ``image.info`` in place while preserving the ``transparency`` entry.

    Pillow stores the transparent color/index of palette (``P``), grayscale
    (``L``) and ``RGB`` images (PNG ``tRNS`` chunk, GIF transparency index) in
    ``info["transparency"]``. Clearing ``info`` blindly makes transparent
    pixels render opaque and hides the transparency from ``has_transparency``.

    EXIF, XMP, ICC profile, text chunks and any other entry are removed.
    A value of ``0`` is a valid palette index, so only ``None`` is treated as
    "absent".

    Args:
        image (Image.Image): Image whose ``info`` dictionary is sanitized.

    Returns:
        Image.Image: The same image instance, to allow chaining.
    """
    transparency = image.info.get("transparency")
    image.info.clear()
    if transparency is not None:
        image.info["transparency"] = transparency
    return image
