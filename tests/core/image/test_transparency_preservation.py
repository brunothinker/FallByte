"""Stripping metadata must keep `transparency` (P / L / RGB images, GIF, PNG)."""

from pathlib import Path

import pytest
from PIL import Image

from src.image.image_file_compression import file_compressor
from src.image.image_file_metadata import file_metadata_remover
from src.image.utils.image_metadata_utils import clear_metadata_keep_transparency
from src.image.utils.image_remove_transparency import has_transparency


def _make_p_png(path: Path) -> None:
    img = Image.new("P", (16, 16), 0)
    img.putpalette([255, 0, 0, 0, 255, 0] + [0] * 756)
    img.paste(1, (8, 0, 16, 16))
    img.info["transparency"] = 0
    img.save(path, transparency=0)


def _make_p_gif(path: Path) -> None:
    img = Image.new("P", (16, 16), 0)
    img.putpalette([255, 0, 0, 0, 255, 0] + [0] * 756)
    img.paste(1, (8, 0, 16, 16))
    img.save(path, transparency=0)


def _make_rgb_trns_png(path: Path) -> None:
    img = Image.new("RGB", (16, 16), (255, 0, 0))
    img.paste((0, 255, 0), (8, 0, 16, 16))
    img.save(path, transparency=(255, 0, 0))


def _make_l_trns_png(path: Path) -> None:
    img = Image.new("L", (16, 16), 10)
    img.paste(200, (8, 0, 16, 16))
    img.save(path, transparency=10)


def _alpha_at(img: Image.Image, xy: tuple[int, int]) -> int:
    """Alpha value of a pixel (type-safe wrapper around `getpixel`)."""
    pixel = img.convert("RGBA").getpixel(xy)
    assert isinstance(pixel, tuple)
    return int(pixel[3])


def _alpha_of_left_half(path: Path) -> int:
    with Image.open(path) as img:
        return _alpha_at(img, (0, 0))


def _alpha_of_right_half(path: Path) -> int:
    with Image.open(path) as img:
        return _alpha_at(img, (15, 0))


CASES = [
    ("p.png", _make_p_png),
    ("p.gif", _make_p_gif),
    ("rgb_trns.png", _make_rgb_trns_png),
    ("l_trns.png", _make_l_trns_png),
]


def test_helper_keeps_transparency_and_drops_rest() -> None:
    img = Image.new("P", (2, 2))
    img.info.update({"transparency": 0, "exif": b"x", "icc_profile": b"y"})
    clear_metadata_keep_transparency(img)
    assert img.info == {"transparency": 0}


def test_helper_without_transparency_clears_everything() -> None:
    img = Image.new("RGB", (2, 2))
    img.info.update({"exif": b"x", "dpi": (72, 72)})
    clear_metadata_keep_transparency(img)
    assert img.info == {}


@pytest.mark.parametrize(("name", "maker"), CASES)
def test_metadata_remover_preserves_transparency(
    tmp_path: Path, name: str, maker
) -> None:
    src, dst = tmp_path / name, tmp_path / f"out_{name}"
    maker(src)
    assert _alpha_of_left_half(src) == 0

    assert file_metadata_remover(src, dst) is True

    assert _alpha_of_left_half(dst) == 0
    assert _alpha_of_right_half(dst) == 255


@pytest.mark.parametrize(("name", "maker"), CASES)
@pytest.mark.parametrize("quality", [100, 60])
def test_compressor_strip_preserves_transparency(
    tmp_path: Path, name: str, maker, quality: int
) -> None:
    if name.endswith(".gif"):
        pytest.skip("GIF is copied unchanged by the compressor")
    src, dst = tmp_path / name, tmp_path / f"out_{name}"
    maker(src)

    assert file_compressor(src, dst, quality=quality, strip_metadata=True) is True

    assert _alpha_of_left_half(dst) == 0
    assert _alpha_of_right_half(dst) == 255


def test_png_quantization_keeps_transparency_after_strip(tmp_path: Path) -> None:
    src, dst = tmp_path / "p.png", tmp_path / "out.png"
    _make_p_png(src)
    assert file_compressor(src, dst, quality=50, strip_metadata=True)
    with Image.open(dst) as out:
        assert has_transparency(out)


def test_animated_gif_keeps_per_frame_transparency(tmp_path: Path) -> None:
    src, dst = tmp_path / "anim.gif", tmp_path / "out.gif"
    frames = []
    for color in (1, 2):
        f = Image.new("P", (16, 16), 0)
        f.putpalette([255, 0, 0, 0, 255, 0, 0, 0, 255] + [0] * 756)
        f.paste(color, (8, 0, 16, 16))
        frames.append(f)
    frames[0].save(
        src, save_all=True, append_images=frames[1:], duration=[50, 80], loop=0,
        transparency=0,
    )

    assert file_metadata_remover(src, dst) is True

    with Image.open(dst) as out:
        n_frames = getattr(out, "n_frames", 1)
        assert n_frames == 2
        for i in range(n_frames):
            out.seek(i)
            assert _alpha_at(out, (0, 0)) == 0
