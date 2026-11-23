"""Core (image): testes de conversion (engines de arquivo e de diretorio)."""

import pillow_heif
import pytest
from PIL import Image

from src.formats import IMAGE_TARGET_FORMATS
from src.image import image_directory_conversion as image_conversion
from src.image.image_file_conversion import file_converter


def test_image_batch_conversion_avoids_output_name_collisions(
    tmp_workspace, monkeypatch
):
    """Ensures image batch conversion creates distinct outputs for matching stems."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "photo.png").write_bytes(b"png source")
    (in_dir / "photo.jpg").write_bytes(b"jpg source")

    def fake_converter(
        input_path,
        output_path,
        target_format,
        transparency_replacement_color,
        **_kwargs,
    ):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(input_path.read_bytes())
        return True

    monkeypatch.setattr(image_conversion, "file_converter", fake_converter)

    stats = image_conversion.directory_converter(in_dir, out_dir, target_format="webp")

    outputs = list((out_dir / "converted").glob("*.webp"))

    assert stats["success"] == 2, (
        "[batch] Both same-stem images must convert without overwriting each other."
    )
    assert stats["failed"] == 0, (
        "[batch] Expected 0 failures during image stem-collision conversion."
    )
    assert len(outputs) == 2, (
        "[batch] Destination folder must contain 2 separate WebP files rather than overwriting one."
    )
    assert len({path.name for path in outputs}) == 2, (
        "[batch] Output filenames for same-stem images must be deduplicated."
    )
    assert {path.read_bytes() for path in outputs} == {
        b"png source",
        b"jpg source",
    }, "[batch] Both source payloads must be preserved independently without data loss."
    assert stats["compressed_bytes"] == sum(path.stat().st_size for path in outputs), (
        "[batch] compressed_bytes statistic must sum the sizes of all distinct output files."
    )


def test_image_batch_conversion_preserves_existing_output(tmp_workspace, monkeypatch):
    """Ensures image batch conversion does not overwrite an existing destination."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "photo.png").write_bytes(b"png source")

    previous_session = out_dir / "converted"
    previous_session.mkdir(parents=True)

    existing_output = previous_session / "photo.webp"
    existing_output.write_bytes(b"existing user data")

    def fake_converter(
        input_path,
        output_path,
        target_format,
        transparency_replacement_color,
        **_kwargs,
    ):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(input_path.read_bytes())
        return True

    monkeypatch.setattr(image_conversion, "file_converter", fake_converter)

    stats = image_conversion.directory_converter(in_dir, out_dir, target_format="webp")

    assert stats["success"] == 1, (
        "[batch] Batch conversion must succeed when an earlier session folder already exists."
    )
    assert existing_output.read_bytes() == b"existing user data", (
        "[batch] Pre-existing user output in an earlier 'converted' folder must never be overwritten."
    )

    new_session = out_dir / "converted_1"
    assert new_session.is_dir(), (
        "[batch] New batch run must allocate 'converted_1' alongside the existing 'converted' folder."
    )
    assert (new_session / "photo.webp").exists(), (
        "[batch] New session folder must hold the output with the original file name."
    )
    assert len(list(out_dir.rglob("*.webp"))) == 2, (
        "[batch] Both the pre-existing WebP and newly converted WebP must exist across sessions."
    )


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

    assert success is True, (
        f"[image] Conversion from {source_mode} to {target_fmt} unexpectedly returned False."
    )
    assert dst_path.exists(), (
        f"[image] Converted output file '{dst_path}' was not created on disk."
    )
    assert dst_path.stat().st_size > 0, (
        f"[image] Converted output file '{dst_path}' is empty (0 bytes)."
    )


def test_heic_image_conversion_to_target_formats(tmp_workspace, create_sample_image):
    """Verifies HEIC/HEIF image input conversion to other supported target formats."""
    in_dir, out_dir = tmp_workspace

    base_png = in_dir / "sample.png"
    create_sample_image(base_png, mode="RGB", size=(100, 100), fmt="PNG")

    heif_file = pillow_heif.from_pillow(Image.open(base_png))
    src_heic = in_dir / "sample.heic"
    heif_file.save(src_heic)

    dst_jpeg = out_dir / "converted_heic.jpg"
    success = file_converter(
        src_heic,
        dst_jpeg,
        target_format="JPEG",
        transparency_replacement_color="#FFFFFF",
    )

    assert success is True, (
        "[image] HEIC-to-JPEG conversion returned False; pillow-heif opener may not be active."
    )
    assert dst_jpeg.exists(), (
        "[image] Converted JPEG file from HEIC source was not written to disk."
    )
    assert dst_jpeg.stat().st_size > 0, (
        "[image] Converted JPEG file from HEIC source is empty."
    )

    with Image.open(dst_jpeg) as img:
        assert img.format == "JPEG", (
            f"[image] Expected output container format 'JPEG', got '{img.format}'."
        )


def test_ico_sizing_clamp(tmp_workspace, create_sample_image):
    """Verifies that ICO conversion clamps dimensions to maximum allowable 256x256."""
    in_dir, out_dir = tmp_workspace
    large_png = in_dir / "large.png"
    create_sample_image(large_png, mode="RGBA", size=(500, 500), fmt="PNG")

    dst_ico = out_dir / "icon.ico"
    success = file_converter(large_png, dst_ico, target_format="ICO")

    assert success is True, (
        "[image] ICO conversion of a 500x500 PNG unexpectedly returned False."
    )
    assert dst_ico.exists(), "[image] Converted ICO file was not written to disk."

    with Image.open(dst_ico) as img:
        assert img.size[0] <= 256, (
            f"[image] ICO width {img.size[0]}px exceeded the 256px specification ceiling."
        )
        assert img.size[1] <= 256, (
            f"[image] ICO height {img.size[1]}px exceeded the 256px specification ceiling."
        )


def test_image_conversion_atomic_write_on_failure(tmp_workspace, monkeypatch):
    """Ensures conversion failures do not corrupt pre-existing files or leave temp files."""
    in_dir, out_dir = tmp_workspace
    src_img = in_dir / "corrupted.png"
    src_img.write_bytes(b"invalid image data")

    dst_img = out_dir / "output.jpg"
    dst_img.write_bytes(b"pre-existing target data")

    success = file_converter(src_img, dst_img, target_format="JPEG")

    assert success is False, (
        "[image] Converting corrupted image bytes must return False."
    )
    assert dst_img.exists(), (
        "[image] Failed conversion must not delete a pre-existing destination file."
    )
    assert dst_img.read_bytes() == b"pre-existing target data", (
        "[image] Failed conversion must not corrupt or overwrite pre-existing destination bytes."
    )
    assert list(out_dir.glob(".*_tmp_*")) == [], (
        "[image] Failed image conversion leaked temporary artifacts in the output directory."
    )
