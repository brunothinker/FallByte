"""Image engine tests: single-file conversion and compression.

Covers the color-mode x target-format conversion matrix, ICO size clamping and
the "keep original" fallback of the image compressor.
"""

import pytest
from PIL import Image

from src.image.image_file_compression import file_compressor
from src.image.image_file_conversion import file_converter

IMAGE_TARGET_FORMATS = ["JPEG", "PNG", "WEBP", "BMP", "ICO", "TIFF"]


# --- Conversion ---


@pytest.mark.parametrize("source_mode", ["RGB", "RGBA", "P", "CMYK"])
@pytest.mark.parametrize("target_fmt", IMAGE_TARGET_FORMATS)
def test_image_conversion_matrix(
    tmp_workspace, create_sample_image, source_mode, target_fmt
):
    """Tests full image format and color mode conversion matrix."""
    in_dir, out_dir = tmp_workspace
    ext = "jpg" if target_fmt == "JPEG" else target_fmt.lower()

    # CMYK cannot be stored as PNG, so it is generated as TIFF.
    src_fmt = "TIFF" if source_mode == "CMYK" else "PNG"
    src_ext = "tiff" if source_mode == "CMYK" else "png"

    src_img = in_dir / f"sample_{source_mode}.{src_ext}"
    if not src_img.exists():
        create_sample_image(src_img, mode=source_mode, fmt=src_fmt)

    dst_path = out_dir / f"converted_{source_mode}_to_{target_fmt.lower()}.{ext}"

    success = file_converter(
        src_img,
        dst_path,
        target_format=target_fmt,
        transparency_replacement_color="#FFFFFF",
    )

    assert success is True
    assert dst_path.exists()
    assert dst_path.stat().st_size > 0


def test_ico_sizing_clamp(tmp_workspace, create_sample_image):
    """Verifies that ICO conversion clamps dimensions to maximum allowable 256x256."""
    in_dir, out_dir = tmp_workspace
    large_png = in_dir / "large.png"
    create_sample_image(large_png, mode="RGBA", size=(500, 500), fmt="PNG")

    dst_ico = out_dir / "icon.ico"
    success = file_converter(large_png, dst_ico, target_format="ICO")

    assert success is True
    assert dst_ico.exists()

    with Image.open(dst_ico) as img:
        assert img.size[0] <= 256
        assert img.size[1] <= 256


def test_image_conversion_atomic_write_on_failure(tmp_workspace, monkeypatch):
    """Ensures conversion failures do not corrupt pre-existing files or leave temp files."""
    in_dir, out_dir = tmp_workspace
    src_img = in_dir / "corrupted.png"
    src_img.write_bytes(b"invalid image data")

    dst_img = out_dir / "output.jpg"
    dst_img.write_bytes(b"pre-existing target data")

    success = file_converter(src_img, dst_img, target_format="JPEG")

    assert success is False
    assert dst_img.exists()
    assert dst_img.read_bytes() == b"pre-existing target data"
    assert list(out_dir.glob(".*_tmp_*")) == []


# --- Compression ---


def test_image_compression_keep_original_when_uncompressible(
    tmp_workspace, create_sample_image
):
    """Ensures image compression fallback handles formats without compression gains cleanly."""
    in_dir, out_dir = tmp_workspace
    src_gif = in_dir / "sample.gif"
    create_sample_image(src_gif, mode="P", fmt="GIF")

    dst_gif = out_dir / "compressed.gif"
    success = file_compressor(src_gif, dst_gif, quality=80)

    assert success is True
    assert dst_gif.exists()