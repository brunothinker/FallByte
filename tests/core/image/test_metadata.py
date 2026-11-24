"""Tests for single-file and batch directory image metadata removal (`src/image/image_file_metadata.py` & `src/image/image_directory_metadata.py`)."""

import threading

import pillow_heif
import pytest
from PIL import Image, PngImagePlugin

from src.image.image_directory_metadata import directory_metadata_remover
from src.image.image_file_metadata import file_metadata_remover


@pytest.mark.parametrize(
    ("src_fmt", "ext", "mode"),
    [
        ("JPEG", "jpg", "RGB"),
        ("PNG", "png", "RGBA"),
        ("WEBP", "webp", "RGBA"),
        ("TIFF", "tiff", "RGB"),
        ("BMP", "bmp", "RGB"),
    ],
)
def test_image_metadata_removal_formats_strip_exif_and_icc(
    tmp_workspace, src_fmt, ext, mode
):
    """Tests single-file metadata stripping across supported formats removes EXIF and ICC profiles."""
    in_dir, out_dir = tmp_workspace
    src_img = in_dir / f"tagged.{ext}"

    img = Image.new(mode, (120, 80), color=(40, 120, 200))
    exif = img.getexif()
    exif[271] = "TestCameraBrand"  # Make
    exif[272] = "Model-X99"  # Model
    exif[34853] = {1: "S", 2: (19.0, 49.0, 0.0)}  # GPSInfo
    fake_icc = b"fake-icc-profile-payload"

    save_kwargs: dict = {}
    if src_fmt in ("JPEG", "PNG", "WEBP", "TIFF"):
        save_kwargs["exif"] = exif.tobytes()
        save_kwargs["icc_profile"] = fake_icc

    img.save(src_img, format=src_fmt, **save_kwargs)

    dst_img = out_dir / f"clean.{ext}"
    res = file_metadata_remover(src_img, dst_img)

    assert res.is_processed, (
        f"[image] Stripping metadata from {src_fmt} unexpectedly failed or skipped: {res}."
    )
    assert dst_img.exists(), (
        f"[image] Sanitized output file '{dst_img}' was not written to disk."
    )

    with Image.open(dst_img) as out_img:
        assert out_img.size == (120, 80), (
            f"[image] Metadata removal must preserve image dimensions for {src_fmt}."
        )
        out_exif = out_img.getexif()
        for sensitive_tag in (271, 272, 34853):
            assert sensitive_tag not in out_exif, (
                f"[image] Output {src_fmt} must strip sensitive tag {sensitive_tag}."
            )
        if src_fmt != "TIFF":
            assert len(out_exif) == 0, (
                f"[image] Output {src_fmt} must have zero EXIF tags."
            )
        assert "icc_profile" not in out_img.info, (
            f"[image] Output {src_fmt} must not retain embedded ICC profile."
        )
        assert "exif" not in out_img.info, (
            f"[image] Output {src_fmt} info dictionary must not contain raw EXIF bytes."
        )


def test_image_metadata_removal_strips_png_text_chunks(tmp_workspace):
    """Verifies PNG textual metadata chunks (tEXt/iTXt/XMP) are completely stripped."""
    in_dir, out_dir = tmp_workspace
    src_png = in_dir / "chunks.png"

    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text("Author", "Secret User")
    pnginfo.add_text("XML:com.adobe.xmp", "<x:xmpmeta>GPS=123</x:xmpmeta>")
    pnginfo.add_itxt("Comment", "Private camera note")

    img = Image.new("RGBA", (100, 100), color=(255, 0, 128, 200))
    img.save(src_png, format="PNG", pnginfo=pnginfo)

    dst_png = out_dir / "chunks_clean.png"
    res = file_metadata_remover(src_png, dst_png)

    assert res.is_processed, f"[image] PNG metadata removal failed: {res}."
    with Image.open(dst_png) as out_img:
        assert "Author" not in out_img.info, (
            "[image] PNG tEXt 'Author' chunk was not stripped."
        )
        assert "XML:com.adobe.xmp" not in out_img.info, (
            "[image] PNG XMP metadata chunk was not stripped."
        )
        assert "Comment" not in out_img.info, (
            "[image] PNG iTXt 'Comment' chunk was not stripped."
        )


def test_image_metadata_removal_preserves_exif_orientation(tmp_workspace):
    """Ensures EXIF orientation tag is baked into pixel layout before stripping EXIF tags."""
    in_dir, out_dir = tmp_workspace
    src_jpg = in_dir / "portrait_exif.jpg"

    # Stored as 300x150 landscape, but EXIF Orientation=6 rotates it 90 deg CW to 150x300 portrait
    img = Image.new("RGB", (300, 150), color=(10, 200, 90))
    exif = img.getexif()
    exif[274] = 6  # Orientation: Rotate 90 CW
    exif[271] = "PhoneVendor"
    img.save(src_jpg, format="JPEG", exif=exif.tobytes())

    dst_jpg = out_dir / "portrait_clean.jpg"
    res = file_metadata_remover(src_jpg, dst_jpg)

    assert res.is_processed, f"[image] Metadata removal on EXIF-rotated JPEG failed: {res}."
    with Image.open(dst_jpg) as out_img:
        assert out_img.size == (150, 300), (
            f"[image] Expected baked portrait dimensions (150, 300), got {out_img.size}."
        )
        assert len(out_img.getexif()) == 0, (
            "[image] EXIF tags must be completely removed after orientation transpose."
        )


def test_image_metadata_removal_animated_gif_preserves_frames_and_strips_comment(
    tmp_workspace,
):
    """Verifies multi-frame animated GIF strips comment metadata while preserving animation frames."""
    in_dir, out_dir = tmp_workspace
    src_gif = in_dir / "anim_comment.gif"

    frames = [
        Image.new("RGB", (120, 80), color=(255, 0, 0)),
        Image.new("RGB", (120, 80), color=(0, 255, 0)),
    ]
    frames[0].save(
        src_gif,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
        comment=b"Sensitive device comment",
    )

    dst_gif = out_dir / "anim_clean.gif"
    res = file_metadata_remover(src_gif, dst_gif)

    assert res.is_processed, f"[image] Animated GIF metadata removal failed: {res}."
    with Image.open(dst_gif) as out_gif:
        assert getattr(out_gif, "n_frames", 1) == 2, (
            "[image] Sanitized animated GIF lost animation frames."
        )
        assert out_gif.size == (120, 80)
        assert "comment" not in out_gif.info, (
            "[image] GIF comment metadata was not stripped."
        )


def test_heic_image_metadata_removal_saves_clean_png(tmp_workspace, create_sample_image):
    """Ensures HEIC images are decoded via pillow-heif and saved as clean PNG without metadata."""
    in_dir, out_dir = tmp_workspace
    base_png = in_dir / "base.png"
    create_sample_image(base_png, mode="RGB", size=(200, 120), fmt="PNG")

    pil_img = Image.open(base_png)
    exif = pil_img.getexif()
    exif[271] = "Apple"
    heif_file = pillow_heif.from_pillow(pil_img)
    src_heic = in_dir / "photo.heic"
    heif_file.save(src_heic, exif=exif.tobytes())

    dst_png = out_dir / "photo_clean.png"
    res = file_metadata_remover(src_heic, dst_png)

    assert res.is_processed, f"[image] HEIC metadata removal failed: {res}."
    assert dst_png.exists(), "[image] Clean PNG output from HEIC source was not created."
    with Image.open(dst_png) as out_img:
        assert out_img.format == "PNG"
        assert out_img.size == (200, 120)
        assert len(out_img.getexif()) == 0, (
            "[image] Output PNG converted from HEIC must contain zero EXIF tags."
        )


def test_image_metadata_removal_atomic_write_on_failure(tmp_workspace):
    """Ensures metadata removal failures leave pre-existing files untouched and leak no temp files."""
    in_dir, out_dir = tmp_workspace
    src_corrupted = in_dir / "corrupted.jpg"
    src_corrupted.write_bytes(b"corrupted header bytes")

    dst_img = out_dir / "existing.jpg"
    dst_img.write_bytes(b"intact existing file")

    res = file_metadata_remover(src_corrupted, dst_img)

    assert res.is_failed and not res, (
        f"[image] Stripping corrupted bytes must return failed FileResult, got {res}."
    )
    assert dst_img.exists(), (
        "[image] Failed metadata removal must not unlink pre-existing destination file."
    )
    assert dst_img.read_bytes() == b"intact existing file", (
        "[image] Failed metadata removal must leave pre-existing destination bytes untouched."
    )
    assert list(out_dir.glob(".*_tmp_*")) == [], (
        "[image] Failed metadata removal leaked temporary artifacts in output directory."
    )


def test_directory_metadata_remover_preserves_hierarchy_and_strips_tags(tmp_workspace):
    """Verifies batch directory metadata removal preserves folder structure and cleans all files."""
    in_dir, out_dir = tmp_workspace
    nested_dir = in_dir / "trip" / "day1"
    nested_dir.mkdir(parents=True)

    root_jpg = in_dir / "cover.jpg"
    nested_png = nested_dir / "landmark.png"

    jpg_img = Image.new("RGB", (160, 120), color=(90, 140, 210))
    exif = jpg_img.getexif()
    exif[271] = "CameraCorp"
    jpg_img.save(root_jpg, format="JPEG", exif=exif.tobytes())

    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text("Software", "SecretEditor")
    png_img = Image.new("RGBA", (140, 100), color=(200, 80, 60, 255))
    png_img.save(nested_png, format="PNG", pnginfo=pnginfo)

    summary = directory_metadata_remover(input_dir=in_dir, output_dir=out_dir)

    assert summary["total_files"] == 2
    assert summary["success"] == 2
    assert summary["failed"] == 0

    session_dirs = [p for p in out_dir.iterdir() if p.is_dir()]
    assert len(session_dirs) == 1, (
        "[image] Batch metadata removal must create exactly one session output directory."
    )
    session_dir = session_dirs[0]

    out_root = session_dir / "cover.jpg"
    out_nested = session_dir / "trip" / "day1" / "landmark.png"
    assert out_root.exists() and out_nested.exists(), (
        "[image] Batch metadata removal did not preserve relative subdirectory hierarchy."
    )

    with Image.open(out_root) as img1, Image.open(out_nested) as img2:
        assert len(img1.getexif()) == 0
        assert "Software" not in img2.info


def test_directory_metadata_remover_remaps_heic_extension_to_png(
    tmp_workspace, create_sample_image
):
    """Ensures HEIC files in batch mode are remapped to .png output files cleanly."""
    in_dir, out_dir = tmp_workspace
    base_png = in_dir / "temp.png"
    create_sample_image(base_png, mode="RGB", size=(150, 150), fmt="PNG")

    src_heic = in_dir / "capture.heic"
    pillow_heif.from_pillow(Image.open(base_png)).save(src_heic)
    base_png.unlink()

    summary = directory_metadata_remover(input_dir=in_dir, output_dir=out_dir)

    assert summary["success"] == 1
    session_dir = next(p for p in out_dir.iterdir() if p.is_dir())
    expected_png = session_dir / "capture.png"
    assert expected_png.exists(), (
        "[image] Batch metadata remover must remap HEIC outputs to '.png' extension."
    )


def test_directory_metadata_remover_empty_folder_returns_no_files(tmp_workspace):
    """Ensures an input directory with no supported images returns no_files=True cleanly."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "readme.txt").write_text("not an image", encoding="utf-8")

    summary = directory_metadata_remover(input_dir=in_dir, output_dir=out_dir)

    assert summary.get("no_files") is True
    assert list(out_dir.iterdir()) == []


def test_directory_metadata_remover_cancellation_cleans_session_files(
    tmp_workspace, create_sample_image
):
    """Ensures triggering cancel_event halts processing and cleans generated session files."""
    in_dir, out_dir = tmp_workspace
    for idx in range(3):
        create_sample_image(
            in_dir / f"img_{idx}.png", mode="RGB", size=(100, 100), fmt="PNG"
        )

    cancel_event = threading.Event()
    cancel_event.set()

    summary = directory_metadata_remover(
        input_dir=in_dir,
        output_dir=out_dir,
        cancel_event=cancel_event,
    )

    assert summary.get("cancelled") is True
    assert list(out_dir.iterdir()) == []
