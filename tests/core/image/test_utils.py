"""Core (image): image_scanner + image_remove_transparency."""

from pathlib import Path

import pytest
from PIL import Image

from src.image.utils.image_remove_transparency import (
    ALPHA_SUPPORTED_FORMATS,
    NON_ALPHA_FORMATS,
    has_transparency,
    remove_transparency,
)
from src.image.utils.image_scanner import scan_image_files


def test_scan_image_files_recursive_and_sorted(tmp_path: Path) -> None:
    """Scans nested directories recursively, filters supported formats case-insensitively, and sorts."""
    sub = tmp_path / "sub"
    sub.mkdir()

    img_b = tmp_path / "b.png"
    img_a = tmp_path / "a.JPG"
    img_nested = sub / "nested.webp"
    ignored_txt = tmp_path / "notes.txt"
    ignored_mp4 = sub / "video.mp4"

    for p in (img_b, img_a, img_nested, ignored_txt, ignored_mp4):
        p.write_bytes(b"data")

    found = scan_image_files(tmp_path, recursive=True)
    assert found == sorted([img_a, img_b, img_nested]), (
        "[core] scan_image_files(recursive=True) must return all supported images sorted alphabetically."
    )


def test_scan_image_files_non_recursive(tmp_path: Path) -> None:
    """Restricts scan to top-level directory when recursive=False."""
    sub = tmp_path / "sub"
    sub.mkdir()

    top_img = tmp_path / "top.png"
    nested_img = sub / "nested.png"
    top_img.write_bytes(b"data")
    nested_img.write_bytes(b"data")

    found = scan_image_files(tmp_path, recursive=False)
    assert found == [top_img], (
        "[core] scan_image_files(recursive=False) must ignore nested subdirectories."
    )


def test_scan_image_files_invalid_or_missing_directory(tmp_path: Path) -> None:
    """Returns an empty list without raising when path does not exist or is a regular file."""
    missing = tmp_path / "does_not_exist"
    assert scan_image_files(missing) == [], (
        "[core] Missing directory must yield an empty list."
    )

    regular_file = tmp_path / "file.png"
    regular_file.write_bytes(b"data")
    assert scan_image_files(regular_file) == [], (
        "[core] Passing a file path instead of a directory must yield an empty list."
    )


@pytest.mark.parametrize("mode", ["RGBA", "LA", "PA"])
def test_has_transparency_detects_alpha_modes(mode: str) -> None:
    """Recognizes all explicit alpha pixel modes."""
    img = Image.new(mode, (4, 4))
    assert has_transparency(img) is True, (
        f"[core] Image in mode '{mode}' must be detected as transparent."
    )


def test_has_transparency_detects_info_key_and_opaque_images() -> None:
    """Detects transparency via info['transparency'] and returns False for opaque RGB/L."""
    opaque_rgb = Image.new("RGB", (4, 4), (255, 0, 0))
    opaque_l = Image.new("L", (4, 4), 128)
    assert has_transparency(opaque_rgb) is False
    assert has_transparency(opaque_l) is False

    palette_with_trns = Image.new("P", (4, 4))
    palette_with_trns.info["transparency"] = 0
    assert has_transparency(palette_with_trns) is True, (
        "[core] Palette image declaring info['transparency'] must report has_transparency=True."
    )


def test_remove_transparency_flattens_over_background_color() -> None:
    """Composites transparent pixels onto the target background color and returns RGB."""
    rgba = Image.new("RGBA", (2, 1), (0, 0, 0, 0))
    rgba.putpixel((0, 0), (255, 0, 0, 0))
    rgba.putpixel((1, 0), (255, 0, 0, 255))

    flattened = remove_transparency(rgba, background_color="#00FF00")
    assert flattened.mode == "RGB", (
        "[core] remove_transparency() must output an RGB image."
    )
    assert flattened.getpixel((0, 0)) == (0, 255, 0), (
        "[core] Fully transparent pixel must take the exact background color."
    )
    assert flattened.getpixel((1, 0)) == (255, 0, 0), (
        "[core] Fully opaque pixel must preserve its original RGB values."
    )


def test_remove_transparency_noop_and_invalid_color_fallback() -> None:
    """Returns original image when opaque and falls back cleanly on invalid hex color."""
    opaque = Image.new("RGB", (4, 4), (10, 20, 30))
    assert remove_transparency(opaque) is opaque, (
        "[core] Opaque image must be returned unchanged by remove_transparency()."
    )

    rgba = Image.new("RGBA", (4, 4), (10, 20, 30, 128))
    fallback = remove_transparency(rgba, background_color="not-a-valid-color")
    assert fallback.mode == "RGB", (
        "[core] Invalid background color must fall back to RGB conversion instead of raising."
    )


def test_alpha_format_constants_are_disjoint() -> None:
    """Ensures ALPHA_SUPPORTED_FORMATS and NON_ALPHA_FORMATS do not overlap."""
    assert ALPHA_SUPPORTED_FORMATS.isdisjoint(NON_ALPHA_FORMATS), (
        "[core] Alpha-capable and non-alpha format sets must be disjoint."
    )
