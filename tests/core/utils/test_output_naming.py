"""Core: output_naming + output_directory."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from src.utils import output_naming as naming
from src.utils.output_directory import create_unique_output_dir

# ---------------------------------------------------------------------------
# output_directory (session folders for batch runs)
# ---------------------------------------------------------------------------


def test_create_unique_output_dir_uses_base_name_first(tmp_path):
    """Uses the plain folder name when it is still free."""
    result = create_unique_output_dir(tmp_path, "compressed")

    assert result == tmp_path / "compressed", (
        "[batch] Expected create_unique_output_dir() to use the unsuffixed base name when free."
    )
    assert result.is_dir(), (
        "[batch] create_unique_output_dir() must materialize the session directory on disk."
    )


def test_create_unique_output_dir_uses_first_available_suffix(tmp_path):
    """Picks the first free numeric suffix and leaves existing folders untouched."""
    for name in ("compressed", "compressed_1", "compressed_3"):
        (tmp_path / name).mkdir()

    result = create_unique_output_dir(tmp_path, "compressed")

    assert result == tmp_path / "compressed_2", (
        "[batch] Expected create_unique_output_dir() to pick the lowest available numeric suffix ('compressed_2')."
    )
    assert result.is_dir(), (
        "[batch] Newly allocated suffixed session directory must exist on disk."
    )
    assert (tmp_path / "compressed").is_dir(), (
        "[batch] Existing base session directory must remain intact."
    )
    assert (tmp_path / "compressed_1").is_dir(), (
        "[batch] Existing 'compressed_1' directory must remain intact."
    )
    assert (tmp_path / "compressed_3").is_dir(), (
        "[batch] Existing 'compressed_3' directory must remain intact."
    )


def test_create_unique_output_dir_creates_missing_parent(tmp_path):
    """Creates the missing parent directories together with the session folder."""
    parent = tmp_path / "nested" / "destination"

    result = create_unique_output_dir(parent, "converted")

    assert result == parent / "converted", (
        "[batch] Expected create_unique_output_dir() to return the nested session path."
    )
    assert result.is_dir(), (
        "[batch] create_unique_output_dir() must recursively create missing parent directories."
    )


def test_create_unique_output_dir_is_safe_for_concurrent_calls(tmp_path):
    """Guarantees distinct folders when called from several threads at once."""

    def create_folder(_):
        return create_unique_output_dir(tmp_path, "converted")

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(create_folder, range(8)))

    assert len(set(results)) == 8, (
        "[batch] Concurrent calls to create_unique_output_dir() collided instead of returning 8 distinct directories."
    )
    assert all(path.is_dir() for path in results), (
        "[batch] Every directory returned by concurrent create_unique_output_dir() calls must exist."
    )
    assert {path.name for path in results} == {
        "converted",
        *(f"converted_{index}" for index in range(1, 8)),
    }, (
        "[batch] Concurrent session folder allocation did not produce the expected sequential suffix set."
    )


# ---------------------------------------------------------------------------
# output_naming: single-file helpers (operation suffix)
# ---------------------------------------------------------------------------


def test_suffix_constants_match_the_naming_rule():
    """The documented operation suffixes must not drift."""
    assert naming.CONVERTED_SUFFIX == "_converted"
    assert naming.COMPRESSED_SUFFIX == "_compressed"
    assert naming.EXTRACTED_SUFFIX == "_extracted"
    assert naming.TRACKS_SUFFIX == "_tracks"
    assert naming.METADATA_SUFFIX == "_clean"
    assert naming.RESIZED_SUFFIX == "_resized"


@pytest.mark.parametrize(
    ("helper", "kwargs", "source_name", "expected_name"),
    [
        (
            "unique_conversion_output_path",
            {"target_format": "webp"},
            "photo.png",
            "photo_converted.webp",
        ),
        (
            "unique_conversion_output_path",
            {"target_format": ".WEBP"},
            "photo.png",
            "photo_converted.webp",
        ),
        ("unique_compression_output_path", {}, "clip.mp4", "clip_compressed.mp4"),
        ("unique_compression_output_path", {}, "PHOTO.JPG", "PHOTO_compressed.jpg"),
        (
            "unique_downscale_output_path",
            {"target_height": 720, "target_format": "mkv"},
            "clip.mkv",
            "clip_720p.mkv",
        ),
        (
            "unique_downscale_output_path",
            {"target_height": 1080},
            "clip.mp4",
            "clip_1080p.mp4",
        ),
        (
            "unique_extraction_output_path",
            {"target_format": "mp3"},
            "clip.mp4",
            "clip_extracted.mp3",
        ),
        ("unique_tracks_output_path", {}, "movie.mkv", "movie_tracks.mkv"),
        (
            "unique_tracks_output_path",
            {"target_format": "mp4"},
            "movie.mkv",
            "movie_tracks.mp4",
        ),
        ("unique_metadata_output_path", {}, "photo.jpg", "photo_clean.jpg"),
        (
            "unique_metadata_output_path",
            {"target_format": "png"},
            "photo.heic",
            "photo_clean.png",
        ),
        ("unique_resize_output_path", {}, "banner.png", "banner_resized.png"),
        (
            "unique_resize_output_path",
            {"target_format": "png"},
            "banner.heic",
            "banner_resized.png",
        ),
    ],
)
def test_single_file_helpers_apply_operation_suffix(
    tmp_path: Path, helper, kwargs, source_name, expected_name
):
    """Every single-file helper must append its operation suffix and keep/replace the extension."""
    result = getattr(naming, helper)(
        input_path=tmp_path / "in" / source_name,
        output_dir=tmp_path / "out",
        **kwargs,
    )

    assert result == tmp_path / "out" / expected_name, (
        f"[naming] {helper}({source_name!r}, {kwargs}) must return '{expected_name}', got '{result.name}'."
    )


@pytest.mark.parametrize(
    ("helper", "kwargs", "suffix_name"),
    [
        ("unique_conversion_output_path", {"target_format": "jpg"}, "photo_converted"),
        ("unique_compression_output_path", {}, "photo_compressed"),
        ("unique_resize_output_path", {}, "photo_resized"),
        ("unique_metadata_output_path", {}, "photo_clean"),
    ],
)
def test_single_file_helpers_use_numeric_suffix_on_disk_collision(
    tmp_path: Path, helper, kwargs, suffix_name
):
    """An existing destination is never reused: `_2`, then `_3`..."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    ext = kwargs.get("target_format", "png")
    source = tmp_path / "in" / "photo.png"

    (out_dir / f"{suffix_name}.{ext}").write_bytes(b"first")
    second = getattr(naming, helper)(input_path=source, output_dir=out_dir, **kwargs)
    assert second == out_dir / f"{suffix_name}_2.{ext}", (
        f"[naming] {helper} must fall back to '_2' when the base name exists."
    )

    second.write_bytes(b"second")
    third = getattr(naming, helper)(input_path=source, output_dir=out_dir, **kwargs)
    assert third == out_dir / f"{suffix_name}_3.{ext}", (
        f"[naming] {helper} must keep counting ('_3') while earlier names exist."
    )


def test_conversion_collision_does_not_embed_source_extension(tmp_path: Path):
    """Single-file conversion uses the same `_2` rule as every other helper."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "photo_converted.jpg").write_bytes(b"existing")

    result = naming.unique_conversion_output_path(
        input_path=tmp_path / "in" / "photo.png",
        output_dir=out_dir,
        target_format="jpg",
    )

    assert result.name == "photo_converted_2.jpg", (
        f"[naming] Conversion collision must produce 'photo_converted_2.jpg', got '{result.name}'."
    )
    assert "png" not in result.name, (
        "[naming] The source extension must no longer be embedded in the converted file name."
    )


def test_allow_overwrite_returns_existing_destination(tmp_path: Path):
    """With allow_overwrite=True an existing candidate is accepted as is."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "clip_compressed.mp4").write_bytes(b"existing")

    result = naming.unique_compression_output_path(
        input_path=tmp_path / "in" / "clip.mp4",
        output_dir=out_dir,
        allow_overwrite=True,
    )

    assert result == out_dir / "clip_compressed.mp4", (
        "[naming] allow_overwrite=True must not force a numeric suffix."
    )


# ---------------------------------------------------------------------------
# output_naming: batch helper (original name, session folder identifies result)
# ---------------------------------------------------------------------------


def test_batch_helper_keeps_original_name_without_suffix(tmp_path: Path):
    """Batch outputs keep the file name; no operation suffix is ever added."""
    result = naming.unique_batch_output_path(
        input_path=tmp_path / "in" / "photo.png",
        output_dir=tmp_path / "out" / "compressed",
    )

    assert result == tmp_path / "out" / "compressed" / "photo.png", (
        f"[naming] Batch output must keep the original name 'photo.png', got '{result.name}'."
    )


def test_batch_helper_preserves_relative_subfolders_and_target_format(tmp_path: Path):
    """The relative path is rebuilt under the session folder and the extension may change."""
    session_dir = tmp_path / "out" / "converted"

    result = naming.unique_batch_output_path(
        input_path=tmp_path / "in" / "album" / "track01.ogg",
        output_dir=session_dir,
        target_format="mp3",
        relative_path=Path("album") / "track01.ogg",
    )

    assert result == session_dir / "album" / "track01.mp3", (
        f"[naming] Expected '{session_dir / 'album' / 'track01.mp3'}', got '{result}'."
    )


def test_batch_helper_resolves_same_stem_collisions_with_reserved_paths(
    tmp_path: Path,
):
    """Different sources mapped to the same target get `_2`, `_3`... without touching disk."""
    session_dir = tmp_path / "out" / "converted"
    reserved: set[str] = set()

    names = [
        naming.unique_batch_output_path(
            input_path=tmp_path / "in" / source,
            output_dir=session_dir,
            target_format="jpg",
            reserved_paths=reserved,
        ).name
        for source in ("song.png", "song.webp", "song.bmp")
    ]

    assert names == ["song.jpg", "song_2.jpg", "song_3.jpg"], (
        f"[naming] Same-stem batch collisions must be numbered in order, got {names}."
    )


def test_batch_helper_reserved_paths_are_case_insensitive(tmp_path: Path):
    """`A.png` and `a.webp` converted to jpg must not collide on case-insensitive filesystems."""
    session_dir = tmp_path / "out" / "converted"
    reserved: set[str] = set()

    first = naming.unique_batch_output_path(
        input_path=tmp_path / "in" / "A.png",
        output_dir=session_dir,
        target_format="jpg",
        reserved_paths=reserved,
    )
    second = naming.unique_batch_output_path(
        input_path=tmp_path / "in" / "a.webp",
        output_dir=session_dir,
        target_format="jpg",
        reserved_paths=reserved,
    )

    assert first.name == "A.jpg"
    assert second.name == "a_2.jpg", (
        f"[naming] Case-folded collision must be resolved with '_2', got '{second.name}'."
    )


def test_batch_helper_respects_existing_files_on_disk(tmp_path: Path):
    """A name already present in the session folder is never reused."""
    session_dir = tmp_path / "out" / "compressed"
    session_dir.mkdir(parents=True)
    (session_dir / "photo.png").write_bytes(b"existing")

    result = naming.unique_batch_output_path(
        input_path=tmp_path / "in" / "photo.png",
        output_dir=session_dir,
    )

    assert result.name == "photo_2.png", (
        f"[naming] Existing batch output must be preserved; expected 'photo_2.png', got '{result.name}'."
    )
