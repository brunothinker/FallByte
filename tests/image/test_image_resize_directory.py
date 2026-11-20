"""Tests for batch directory image resizing (`src/image/image_directory_resize.py`)."""

import threading

import pillow_heif
from PIL import Image

from src.image.image_directory_resize import directory_resizer


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
