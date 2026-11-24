"""Core (image): tests from compression"""

import threading

import pillow_heif
from PIL import Image, PngImagePlugin

from src.image import image_directory_compression as image_compression
from src.image.image_directory_compression import directory_compressor
from src.image.image_file_compression import file_compressor


def test_image_batch_cancellation_removes_empty_session_folder(
    tmp_workspace, monkeypatch
):
    """Ensures image batch cancellation removes leftover empty session folder."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "photo.png").write_bytes(b"image data")

    cancel_event = threading.Event()
    cancel_event.set()

    stats = image_compression.directory_compressor(
        in_dir, out_dir, quality=80, cancel_event=cancel_event
    )

    assert stats["cancelled"] is True, (
        "[batch] Pre-set cancel_event must mark image batch stats as cancelled=True."
    )
    assert list(out_dir.iterdir()) == [], (
        "[batch] Cancelled image batch must remove its empty session folder from output_dir."
    )


def test_image_compression_keep_original_when_uncompressible(
    tmp_workspace, create_sample_image
):
    """Ensures image compression fallback handles formats without compression gains cleanly."""
    in_dir, out_dir = tmp_workspace
    src_gif = in_dir / "sample.gif"
    create_sample_image(src_gif, mode="P", fmt="GIF")

    dst_gif = out_dir / "compressed.gif"
    res = file_compressor(src_gif, dst_gif, quality=80)

    assert (
        res
        and res.is_skipped
        and res.reason_key == "skip_uncompressible_format"
        and res.reason_params.get("fmt") == "GIF"
    ), (
        f"[image] Compressing uncompressible GIF format must return skipped ('skip_uncompressible_format'), got {res}."
    )
    assert dst_gif.exists(), (
        "[image] Keep-original fallback must still copy the GIF file to the destination path."
    )


def test_heic_image_compression_keeps_original(tmp_workspace, create_sample_image):
    """Ensures HEIC files are handled safely by keeping the original file untouched."""
    in_dir, out_dir = tmp_workspace

    base_png = in_dir / "sample.png"
    create_sample_image(base_png, mode="RGB", size=(100, 100), fmt="PNG")

    heif_file = pillow_heif.from_pillow(Image.open(base_png))
    src_heic = in_dir / "sample.heic"
    heif_file.save(src_heic)

    dst_heic = out_dir / "compressed.heic"
    res = file_compressor(src_heic, dst_heic, quality=80)

    assert (
        res
        and res.is_skipped
        and res.reason_key == "skip_uncompressible_format"
        and res.reason_params.get("fmt") == "HEIF"
    ), (
        f"[image] HEIC compression must return skipped ('skip_uncompressible_format') via atomic copy, got {res}."
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

    def failing_copy2(*args, **kwargs):
        raise OSError("Simulated disk error during copy")

    monkeypatch.setattr("src.utils.cleanup.shutil.copy2", failing_copy2)

    res = file_compressor(src_gif, dst_gif, quality=80)

    assert res.is_failed and not res, (
        f"[image] Simulated I/O error during atomic keep-original copy must return failed FileResult, got {res}."
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


def test_file_compressor_strip_metadata_flag(tmp_workspace):
    """Verifies strip_metadata=True removes EXIF, GPS, and ICC data while strip_metadata=False preserves them."""
    in_dir, out_dir = tmp_workspace
    src_jpg = in_dir / "photo_meta.jpg"

    img = Image.new("RGB", (240, 120), color=(30, 110, 220))
    exif = img.getexif()
    exif[271] = "CameraBrand"
    exif[274] = 6
    exif[34853] = {1: "S", 2: (19.0, 49.0, 0.0)}
    img.save(
        src_jpg,
        format="JPEG",
        quality=98,
        exif=exif.tobytes(),
        icc_profile=b"fake-icc-data",
    )

    dst_keep = out_dir / "keep_meta.jpg"
    res_keep = file_compressor(src_jpg, dst_keep, quality=80, strip_metadata=False)
    assert res_keep.is_processed, f"[image] Expected processed FileResult, got {res_keep}."
    with Image.open(dst_keep) as kept_img:
        assert kept_img.size == (120, 240)
        assert kept_img.getexif().get(271) == "CameraBrand"
        assert "icc_profile" in kept_img.info

    dst_strip = out_dir / "strip_meta.jpg"
    res_strip = file_compressor(src_jpg, dst_strip, quality=80, strip_metadata=True)
    assert res_strip.is_processed, f"[image] Expected processed FileResult, got {res_strip}."
    with Image.open(dst_strip) as clean_img:
        assert clean_img.size == (120, 240), (
            "[image] Display orientation must be preserved when strip_metadata=True."
        )
        assert len(clean_img.getexif()) == 0, (
            "[image] EXIF and GPS tags must be stripped when strip_metadata=True."
        )
        assert "icc_profile" not in clean_img.info, (
            "[image] Embedded ICC profile must be stripped when strip_metadata=True."
        )


def test_file_compressor_strip_metadata_removes_png_chunks_even_without_size_gain(
    tmp_workspace,
):
    """Ensures strip_metadata=True strips PNG text chunks even if compressed output is not smaller."""
    in_dir, out_dir = tmp_workspace
    src_png = in_dir / "tagged.png"

    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text("Author", "Private User")
    pnginfo.add_text("XML:com.adobe.xmp", "<x:xmpmeta>Secret</x:xmpmeta>")

    img = Image.new("RGBA", (32, 32), color=(15, 190, 120, 255))
    img.save(src_png, format="PNG", pnginfo=pnginfo)

    dst_png = out_dir / "stripped.png"
    res = file_compressor(src_png, dst_png, quality=95, strip_metadata=True)
    assert res.is_processed, (
        f"[image] strip_metadata=True must return processed even without size reduction, got {res}."
    )

    with Image.open(dst_png) as out_img:
        assert "Author" not in out_img.info
        assert "XML:com.adobe.xmp" not in out_img.info


def test_directory_compressor_forwards_strip_metadata(tmp_workspace):
    """Verifies batch directory_compressor strips metadata across processed files when enabled."""
    in_dir, out_dir = tmp_workspace
    src_jpg = in_dir / "batch_photo.jpg"

    img = Image.new("RGB", (200, 200), color=(90, 180, 70))
    exif = img.getexif()
    exif[271] = "BatchVendor"
    img.save(src_jpg, format="JPEG", quality=98, exif=exif.tobytes())

    summary = directory_compressor(
        input_dir=in_dir,
        output_dir=out_dir,
        quality=80,
        strip_metadata=True,
    )

    assert summary["success"] == 1
    assert summary["skipped"] == 0
    assert summary["failed"] == 0
    session_dir = next(p for p in out_dir.iterdir() if p.is_dir())
    with Image.open(session_dir / "batch_photo.jpg") as out_img:
        assert len(out_img.getexif()) == 0
