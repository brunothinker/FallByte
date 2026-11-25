"""Core (image): resize tests."""

import threading

import pillow_heif
import pytest
from PIL import Image

from src.image.image_directory_resize import directory_resizer
from src.image.image_file_resize import compute_target_dimensions, file_resizer


def test_compute_target_dimensions_preserves_aspect_ratio():
    """Verifies dimension and percentage math preserve aspect ratio and never upscale."""
    assert compute_target_dimensions(
        1920, 1080, mode="dimension", max_width=960, max_height=960
    ) == (
        960,
        540,
    ), "[image] Landscape image must scale proportionally to fit within max_width."

    assert compute_target_dimensions(
        1080, 1920, mode="dimension", max_width=960, max_height=960
    ) == (
        540,
        960,
    ), "[image] Portrait image must scale proportionally to fit within max_height."

    assert compute_target_dimensions(2000, 1000, mode="percentage", percentage=50) == (
        1000,
        500,
    ), "[image] Percentage scaling at 50% must halve both width and height."

    assert compute_target_dimensions(
        640, 480, mode="dimension", max_width=1920, max_height=1080
    ) == (
        640,
        480,
    ), "[image] Smaller source image must never be upscaled beyond its native resolution."


def test_compute_target_dimensions_invalid_inputs():
    """Ensures invalid dimensions, modes, or percentages raise ValueError."""
    with pytest.raises(ValueError):
        compute_target_dimensions(0, 100, mode="dimension", max_width=50)

    with pytest.raises(ValueError):
        compute_target_dimensions(
            100, 100, mode="dimension", max_width=None, max_height=None
        )

    with pytest.raises(ValueError):
        compute_target_dimensions(100, 100, mode="percentage", percentage=0)

    with pytest.raises(ValueError):
        compute_target_dimensions(100, 100, mode="unknown")


@pytest.mark.parametrize(
    ("src_fmt", "ext", "mode"),
    [
        ("PNG", "png", "RGBA"),
        ("JPEG", "jpg", "RGB"),
        ("WEBP", "webp", "RGBA"),
        ("BMP", "bmp", "RGB"),
        ("TIFF", "tiff", "RGB"),
    ],
)
def test_image_resize_formats_by_dimension(
    tmp_workspace, create_sample_image, src_fmt, ext, mode
):
    """Tests single-file resizing across supported formats preserving aspect ratio."""
    in_dir, out_dir = tmp_workspace
    src_img = in_dir / f"source.{ext}"
    create_sample_image(src_img, mode=mode, size=(800, 400), fmt=src_fmt)

    dst_img = out_dir / f"resized.{ext}"
    res = file_resizer(
        src_img,
        dst_img,
        mode="dimension",
        max_width=400,
        max_height=400,
    )

    assert res.is_processed, (
        f"[image] Resizing {src_fmt} image by dimension unexpectedly failed or skipped: {res}."
    )
    assert dst_img.exists(), (
        f"[image] Resized output file '{dst_img}' was not written to disk."
    )

    with Image.open(dst_img) as img:
        assert img.size == (400, 200), (
            f"[image] Expected resized dimensions (400, 200) for {src_fmt}, got {img.size}."
        )


def test_image_resize_by_percentage(tmp_workspace, create_sample_image):
    """Verifies percentage-based scaling produces accurate proportional output dimensions."""
    in_dir, out_dir = tmp_workspace
    src_png = in_dir / "source.png"
    create_sample_image(src_png, mode="RGBA", size=(600, 300), fmt="PNG")

    dst_png = out_dir / "resized_half.png"
    res = file_resizer(src_png, dst_png, mode="percentage", percentage=50)

    assert res.is_processed, f"[image] Percentage resize failed: {res}."
    with Image.open(dst_png) as img:
        assert img.size == (300, 150), (
            f"[image] Expected 50% scaled size (300, 150), got {img.size}."
        )


def test_image_resize_never_upscales_smaller_images(tmp_workspace, create_sample_image):
    """Ensures smaller images keep their original dimensions when target bounds are larger."""
    in_dir, out_dir = tmp_workspace
    src_png = in_dir / "small.png"
    create_sample_image(src_png, mode="RGB", size=(320, 240), fmt="PNG")

    dst_png = out_dir / "not_upscaled.png"
    res = file_resizer(
        src_png,
        dst_png,
        mode="dimension",
        max_width=1920,
        max_height=1080,
    )

    assert res.is_processed, f"[image] Resize of smaller image failed: {res}."
    with Image.open(dst_png) as img:
        assert img.size == (320, 240), (
            f"[image] Smaller image was unexpectedly upscaled to {img.size}."
        )


def test_image_resize_applies_exif_orientation(tmp_workspace):
    """Ensures EXIF orientation tag (90 deg rotation) is applied before computing dimensions."""
    in_dir, out_dir = tmp_workspace
    src_jpg = in_dir / "rotated.jpg"

    # Stored as 400x200 landscape, but EXIF Orientation=6 rotates it 90 deg to 200x400 portrait
    img = Image.new("RGB", (400, 200), color=(120, 180, 240))
    exif = img.getexif()
    exif[274] = 6  # Orientation: Rotate 90 CW
    img.save(src_jpg, format="JPEG", exif=exif.tobytes())

    dst_jpg = out_dir / "rotated_resized.jpg"
    res = file_resizer(
        src_jpg,
        dst_jpg,
        mode="dimension",
        max_width=200,
        max_height=200,
    )

    assert res.is_processed, f"[image] Resizing EXIF-oriented JPEG failed: {res}."
    with Image.open(dst_jpg) as out_img:
        assert out_img.size == (100, 200), (
            f"[image] Expected portrait output (100, 200) after EXIF transpose, got {out_img.size}."
        )


def test_image_resize_animated_gif_preserves_frames(tmp_workspace):
    """Verifies multi-frame animated GIF resizing scales all frames cleanly."""
    in_dir, out_dir = tmp_workspace
    src_gif = in_dir / "anim.gif"

    frames = [
        Image.new("RGB", (200, 100), color=(255, 0, 0)),
        Image.new("RGB", (200, 100), color=(0, 255, 0)),
    ]
    frames[0].save(
        src_gif,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
    )

    dst_gif = out_dir / "anim_resized.gif"
    res = file_resizer(src_gif, dst_gif, mode="percentage", percentage=50)

    assert res.is_processed, f"[image] Animated GIF resize failed: {res}."
    with Image.open(dst_gif) as out_gif:
        assert getattr(out_gif, "n_frames", 1) == 2, (
            "[image] Resized animated GIF lost animation frames."
        )
        assert out_gif.size == (100, 50), (
            f"[image] Expected resized GIF dimensions (100, 50), got {out_gif.size}."
        )


def test_heic_image_resize_saves_as_png(tmp_workspace, create_sample_image):
    """Ensures HEIC images are decoded via pillow-heif and resized into PNG output."""
    in_dir, out_dir = tmp_workspace
    base_png = in_dir / "base.png"
    create_sample_image(base_png, mode="RGB", size=(400, 200), fmt="PNG")

    heif_file = pillow_heif.from_pillow(Image.open(base_png))
    src_heic = in_dir / "sample.heic"
    heif_file.save(src_heic)

    dst_png = out_dir / "resized_heic.png"
    res = file_resizer(src_heic, dst_png, mode="percentage", percentage=50)

    assert res.is_processed, f"[image] HEIC image resize failed: {res}."
    assert dst_png.exists(), "[image] Resized PNG output from HEIC source was not created."
    with Image.open(dst_png) as img:
        assert img.format == "PNG"
        assert img.size == (200, 100), (
            f"[image] Expected resized HEIC->PNG dimensions (200, 100), got {img.size}."
        )


def test_image_resize_atomic_write_on_failure(tmp_workspace):
    """Ensures resize failures do not corrupt pre-existing files or leak temporary artifacts."""
    in_dir, out_dir = tmp_workspace
    src_corrupted = in_dir / "corrupted.png"
    src_corrupted.write_bytes(b"not a valid image")

    dst_img = out_dir / "existing.png"
    dst_img.write_bytes(b"intact destination content")

    res = file_resizer(src_corrupted, dst_img, mode="percentage", percentage=50)

    assert res.is_failed and not res, (
        f"[image] Resizing corrupted bytes must return failed FileResult, got {res}."
    )
    assert dst_img.exists(), (
        "[image] Failed resize must not unlink pre-existing destination file."
    )
    assert dst_img.read_bytes() == b"intact destination content", (
        "[image] Failed resize must leave pre-existing destination bytes untouched."
    )
    assert list(out_dir.glob(".*_tmp_*")) == [], (
        "[image] Failed image resize leaked temporary artifacts in output directory."
    )


def test_directory_resizer_preserves_hierarchy_and_scales_images(
    tmp_workspace, create_sample_image
):
    """Verifies batch directory resizing preserves nested folder structure and scales files."""
    in_dir, out_dir = tmp_workspace
    nested_dir = in_dir / "vacation" / "2026"
    nested_dir.mkdir(parents=True)

    root_png = in_dir / "banner.png"
    nested_jpg = nested_dir / "photo.jpg"
    create_sample_image(root_png, mode="RGBA", size=(1000, 500), fmt="PNG")
    create_sample_image(nested_jpg, mode="RGB", size=(800, 600), fmt="JPEG")

    summary = directory_resizer(
        input_dir=in_dir,
        output_dir=out_dir,
        mode="dimension",
        max_width=500,
        max_height=500,
    )

    assert summary["total_files"] == 2, (
        f"[image] Expected 2 scanned files, got {summary['total_files']}."
    )
    assert summary["success"] == 2, (
        f"[image] Expected 2 successful resizes, got {summary['success']}."
    )
    assert summary["failed"] == 0, (
        f"[image] Expected 0 failed resizes, got {summary['failed']}."
    )

    session_dirs = [p for p in out_dir.iterdir() if p.is_dir()]
    assert len(session_dirs) == 1, (
        "[image] Batch resize must create exactly one session output directory."
    )
    session_dir = session_dirs[0]

    out_root = session_dir / "banner.png"
    out_nested = session_dir / "vacation" / "2026" / "photo.jpg"
    assert out_root.exists() and out_nested.exists(), (
        "[image] Batch resize did not preserve relative subdirectory hierarchy."
    )

    with Image.open(out_root) as img1, Image.open(out_nested) as img2:
        assert img1.size == (500, 250), (
            f"[image] Expected banner.png size (500, 250), got {img1.size}."
        )
        assert img2.size == (500, 375), (
            f"[image] Expected photo.jpg size (500, 375), got {img2.size}."
        )


def test_directory_resizer_remaps_heic_extension_to_png(
    tmp_workspace, create_sample_image
):
    """Ensures HEIC files in batch mode are remapped to .png output files cleanly."""
    in_dir, out_dir = tmp_workspace
    base_png = in_dir / "temp.png"
    create_sample_image(base_png, mode="RGB", size=(400, 400), fmt="PNG")

    src_heic = in_dir / "capture.heic"
    pillow_heif.from_pillow(Image.open(base_png)).save(src_heic)
    base_png.unlink()

    summary = directory_resizer(
        input_dir=in_dir,
        output_dir=out_dir,
        mode="percentage",
        percentage=50,
    )

    assert summary["success"] == 1
    session_dir = next(p for p in out_dir.iterdir() if p.is_dir())
    expected_png = session_dir / "capture.png"
    assert expected_png.exists(), (
        "[image] Batch resizer must remap HEIC outputs to '.png' extension."
    )
    with Image.open(expected_png) as img:
        assert img.size == (200, 200)


def test_directory_resizer_empty_folder_returns_no_files(tmp_workspace):
    """Ensures an input directory with no supported images returns no_files=True cleanly."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "notes.txt").write_text("not an image", encoding="utf-8")

    summary = directory_resizer(input_dir=in_dir, output_dir=out_dir)

    assert summary.get("no_files") is True, (
        "[image] Empty/unsupported directory must return no_files=True."
    )
    assert list(out_dir.iterdir()) == [], (
        "[image] Empty batch resize must remove empty session directory."
    )


def test_directory_resizer_cancellation_cleans_session_files(
    tmp_workspace, create_sample_image
):
    """Ensures triggering cancel_event halts processing and cleans generated session files."""
    in_dir, out_dir = tmp_workspace
    for idx in range(3):
        create_sample_image(
            in_dir / f"img_{idx}.png", mode="RGB", size=(400, 400), fmt="PNG"
        )

    cancel_event = threading.Event()
    cancel_event.set()

    summary = directory_resizer(
        input_dir=in_dir,
        output_dir=out_dir,
        mode="percentage",
        percentage=50,
        cancel_event=cancel_event,
    )

    assert summary.get("cancelled") is True, (
        "[image] Pre-set cancel_event must mark batch resize summary as cancelled."
    )
    assert list(out_dir.iterdir()) == [], (
        "[image] Cancelled batch resize must clean up its session output folder."
    )
