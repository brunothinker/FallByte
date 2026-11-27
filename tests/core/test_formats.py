"""Core: centralized media format constants, aliases, and normalization helpers."""

import ast
from pathlib import Path

import pytest

from src.formats import (
    AUDIO_TARGET_FORMATS,
    IMAGE_FORMAT_ALIASES,
    IMAGE_TARGET_FORMATS,
    NORMALIZABLE_AUDIO_FORMATS,
    SUPPORTED_AUDIO_EXTENSIONS,
    SUPPORTED_IMAGE_EXTENSIONS,
    SUPPORTED_VIDEO_EXTENSIONS,
    UNCOMPRESSIBLE_AUDIO_FORMATS,
    UNCOMPRESSIBLE_FORMATS,
    UNWRITABLE_IMAGE_FORMATS,
    VIDEO_TARGET_FORMATS,
    normalize_image_format,
)
from src.image import image_file_metadata, image_file_resize


def test_supported_extensions_format_invariants():
    """All supported input extensions must be lowercase and start with a leading dot."""
    for ext_set in (
        SUPPORTED_IMAGE_EXTENSIONS,
        SUPPORTED_VIDEO_EXTENSIONS,
        SUPPORTED_AUDIO_EXTENSIONS,
    ):
        assert ext_set
        assert all(ext.startswith(".") and ext == ext.lower() for ext in ext_set)


def test_target_formats_have_no_dots_or_duplicates():
    """Target output format lists must contain unique, dot-free identifiers."""
    for target_list in (
        IMAGE_TARGET_FORMATS,
        VIDEO_TARGET_FORMATS,
        AUDIO_TARGET_FORMATS,
    ):
        assert len(target_list) == len(set(target_list))
        assert all(not fmt.startswith(".") for fmt in target_list)

    assert all(fmt == fmt.upper() for fmt in IMAGE_TARGET_FORMATS)
    assert all(fmt == fmt.lower() for fmt in VIDEO_TARGET_FORMATS)
    assert all(fmt == fmt.lower() for fmt in AUDIO_TARGET_FORMATS)


def test_normalizable_audio_formats_subset_of_supported_audio():
    """Every normalizable audio format must correspond to a supported audio extension."""
    supported_bare = {ext.lstrip(".") for ext in SUPPORTED_AUDIO_EXTENSIONS}
    assert NORMALIZABLE_AUDIO_FORMATS
    assert NORMALIZABLE_AUDIO_FORMATS.issubset(supported_bare)
    assert all(
        fmt == fmt.lower() and not fmt.startswith(".")
        for fmt in NORMALIZABLE_AUDIO_FORMATS
    )


def test_unwritable_and_uncompressible_sets_are_uppercase_and_synced():
    """Unwritable/uncompressible format sets must use canonical uppercase identifiers."""
    for fmt_set in (
        UNWRITABLE_IMAGE_FORMATS,
        UNCOMPRESSIBLE_FORMATS,
        UNCOMPRESSIBLE_AUDIO_FORMATS,
    ):
        assert fmt_set
        assert all(fmt == fmt.upper() and not fmt.startswith(".") for fmt in fmt_set)

    assert {"HEIC", "HEIF"} == UNWRITABLE_IMAGE_FORMATS
    assert image_file_metadata.UNWRITABLE_METADATA_FORMATS is UNWRITABLE_IMAGE_FORMATS
    assert image_file_resize.UNRESIZABLE_FORMATS is UNWRITABLE_IMAGE_FORMATS


@pytest.mark.parametrize(
    ("raw_format", "path", "expected"),
    [
        ("jpg", None, "JPEG"),
        (".JPG", None, "JPEG"),
        ("mpo", None, "JPEG"),
        ("JFIF", None, "JPEG"),
        ("tif", None, "TIFF"),
        (".heic", None, "HEIF"),
        ("png", None, "PNG"),
        ("WEBP", None, "WEBP"),
        (None, Path("photo.jpg"), "JPEG"),
        (None, Path("camera.MPO"), "JPEG"),
        (None, Path("scan.tif"), "TIFF"),
        (None, Path("apple.heic"), "HEIF"),
        (None, Path("graphic.webp"), "WEBP"),
        ("jpeg", Path("ignored.png"), "JPEG"),
        (None, None, ""),
    ],
)
def test_normalize_image_format(
    raw_format: str | None, path: Path | None, expected: str
):
    """Resolves canonical Pillow format names from explicit format strings or file paths."""
    assert normalize_image_format(raw_format, path) == expected
    if expected in IMAGE_FORMAT_ALIASES.values():
        assert expected not in IMAGE_FORMAT_ALIASES


def test_no_duplicate_format_normalization_definitions_outside_formats():
    """Guards against re-introducing local FORMAT_ALIASES or _normalize_format helpers."""
    repo_root = Path(__file__).resolve().parents[2]
    violations: list[str] = []

    for folder in ("src", "ui"):
        for py_file in (repo_root / folder).rglob("*.py"):
            if py_file == repo_root / "src" / "formats.py":
                continue
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.FunctionDef)
                    and node.name == "_normalize_format"
                ):
                    violations.append(
                        f"{py_file.relative_to(repo_root)}: def _normalize_format"
                    )
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id in {
                            "FORMAT_ALIASES",
                            "NORMALIZABLE_AUDIO_FORMATS",
                        }:
                            violations.append(
                                f"{py_file.relative_to(repo_root)}: {target.id}"
                            )

    assert not violations, (
        f"Duplicate format definitions found outside `src/formats.py`: {violations}"
    )
