"""Core (image): decompression bomb / pixel limit tests across all four image engines."""

import logging

import pytest
from PIL import Image

from src.image.image_file_compression import file_compressor
from src.image.image_file_conversion import file_converter
from src.image.image_file_metadata import file_metadata_remover
from src.image.image_file_resize import file_resizer
from src.image.utils.image_limits import DESKTOP_MAX_IMAGE_PIXELS


def test_default_desktop_pixel_limit_configured() -> None:
    """Ensures image engines raise Pillow's MAX_IMAGE_PIXELS to the documented desktop ceiling."""
    assert DESKTOP_MAX_IMAGE_PIXELS == 250_000_000
    assert Image.MAX_IMAGE_PIXELS == DESKTOP_MAX_IMAGE_PIXELS


@pytest.mark.parametrize(
    ("engine_name", "runner"),
    [
        (
            "conversion",
            lambda src, dst: file_converter(src, dst, target_format="WEBP"),
        ),
        (
            "compression",
            lambda src, dst: file_compressor(src, dst, quality=80),
        ),
        (
            "resize",
            lambda src, dst: file_resizer(
                src, dst, mode="dimension", max_width=50, max_height=50
            ),
        ),
        (
            "metadata",
            file_metadata_remover,
        ),
    ],
)
def test_image_engines_catch_decompression_bomb_with_explicit_message(
    tmp_workspace, monkeypatch, caplog, engine_name, runner
) -> None:
    """Verifies all four image engines catch DecompressionBombError and log explicit MP size."""
    in_dir, out_dir = tmp_workspace
    src_img = in_dir / "oversized_render.png"
    Image.new("RGB", (400, 300), color=(20, 40, 80)).save(src_img, format="PNG")

    # 400 x 300 = 120,000 pixels (0.1 MP) > 2 * 50,000 pixels
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 50_000)

    dst_ext = "webp" if engine_name == "conversion" else "png"
    dst_img = out_dir / f"out_{engine_name}.{dst_ext}"

    with caplog.at_level(logging.ERROR):
        res = runner(src_img, dst_img)

    assert res.is_failed, (
        f"[image] {engine_name} must fail cleanly when image exceeds MAX_IMAGE_PIXELS."
    )
    assert not dst_img.exists(), (
        f"[image] {engine_name} must not leave an output file on DecompressionBombError."
    )
    assert list(out_dir.glob(".*_tmp_*")) == [], (
        f"[image] {engine_name} must clean up temporary files on DecompressionBombError."
    )

    error_messages = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.ERROR
    ]
    assert any(
        "oversized_render.png: image too large (0.1 MP)" in msg
        for msg in error_messages
    ), f"[image] {engine_name} did not log expected explicit size message; got: {error_messages}"
