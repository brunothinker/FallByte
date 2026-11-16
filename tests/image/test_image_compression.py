"""Tests for single-file image compression (`src/image/image_file_compression.py`)."""

import pillow_heif
from PIL import Image

from src.image.image_file_compression import file_compressor


def test_image_compression_keep_original_when_uncompressible(
    tmp_workspace, create_sample_image
):
    """Ensures image compression fallback handles formats without compression gains cleanly."""
    in_dir, out_dir = tmp_workspace
    src_gif = in_dir / "sample.gif"
    create_sample_image(src_gif, mode="P", fmt="GIF")

    dst_gif = out_dir / "compressed.gif"
    success = file_compressor(src_gif, dst_gif, quality=80)

    assert success is True, (
        "[image] Compressing uncompressible GIF format must succeed via keep-original fallback."
    )
    assert dst_gif.exists(), (
        "[image] Keep-original fallback must still copy the GIF file to the destination path."
    )


def test_heic_image_compression_keeps_original(
    tmp_workspace, create_sample_image
):
    """Ensures HEIC files are handled safely by keeping the original file untouched."""
    in_dir, out_dir = tmp_workspace

    base_png = in_dir / "sample.png"
    create_sample_image(base_png, mode="RGB", size=(100, 100), fmt="PNG")

    heif_file = pillow_heif.from_pillow(Image.open(base_png))
    src_heic = in_dir / "sample.heic"
    heif_file.save(src_heic)

    dst_heic = out_dir / "compressed.heic"
    success = file_compressor(src_heic, dst_heic, quality=80)

    assert success is True, (
        "[image] HEIC compression must succeed cleanly via untouched atomic copy."
    )
    assert dst_heic.exists(), (
        "[image] Destination HEIC file was not created during keep-original copy."
    )
    assert dst_heic.read_bytes() == src_heic.read_bytes(), (
        "[image] HEIC compression fallback must preserve exact source bytes without re-encoding."
    )


def test_image_compression_atomic_keep_original_on_failure(
    tmp_workspace, create_sample_image, monkeypatch
):
    """Ensures failure during 'keep_original' copy leaves destination uncorrupted and no tmp files."""
    in_dir, out_dir = tmp_workspace
    src_gif = in_dir / "sample.gif"
    create_sample_image(src_gif, mode="P", fmt="GIF")

    dst_gif = out_dir / "compressed.gif"
    dst_gif.write_bytes(b"original destination data")

    # Force shutil.copy2 to fail during the fallback copy
    def failing_copy2(*args, **kwargs):
        raise OSError("Simulated disk error during copy")

    monkeypatch.setattr("src.utils.cleanup.shutil.copy2", failing_copy2)

    success = file_compressor(src_gif, dst_gif, quality=80)

    assert success is False, (
        "[image] Simulated I/O error during atomic keep-original copy must return False."
    )
    assert dst_gif.exists(), (
        "[image] Failed keep-original copy must not unlink pre-existing destination file."
    )
    assert dst_gif.read_bytes() == b"original destination data", (
        "[image] Failed keep-original copy must leave pre-existing destination bytes intact."
    )
    assert list(out_dir.glob(".*_tmp_*")) == [], (
        "[image] Failed keep-original copy leaked temporary artifacts in the output directory."
    )