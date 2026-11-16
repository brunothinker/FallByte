"""Tests for collision-safe destination naming during batch conversions."""

from src.audio import audio_directory_conversion as audio_conversion
from src.image import image_directory_conversion as image_conversion
from src.video import video_directory_conversion as video_conversion


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


def test_video_batch_conversion_avoids_output_name_collisions(
    tmp_workspace, monkeypatch
):
    """Ensures video batch conversion creates distinct outputs for matching stems."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "clip.avi").write_bytes(b"avi source")
    (in_dir / "clip.mov").write_bytes(b"mov source")

    def fake_converter(
        input_path, output_path, target_format, cancel_event=None, **_kwargs
    ):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(input_path.read_bytes())
        return True

    monkeypatch.setattr(video_conversion, "file_converter", fake_converter)

    stats = video_conversion.directory_converter(in_dir, out_dir, target_format="mp4")

    outputs = list((out_dir / "converted").glob("*.mp4"))

    assert stats["success"] == 2, (
        "[batch] Both same-stem videos must convert without overwriting each other."
    )
    assert stats["failed"] == 0, (
        "[batch] Expected 0 failures during video stem-collision conversion."
    )
    assert len(outputs) == 2, (
        "[batch] Destination folder must contain 2 separate MP4 files rather than overwriting one."
    )
    assert len({path.name for path in outputs}) == 2, (
        "[batch] Output filenames for same-stem videos must be deduplicated."
    )
    assert {path.read_bytes() for path in outputs} == {
        b"avi source",
        b"mov source",
    }, (
        "[batch] Both video source payloads must be preserved independently without data loss."
    )
    assert stats["compressed_bytes"] == sum(path.stat().st_size for path in outputs), (
        "[batch] compressed_bytes statistic must sum the sizes of all distinct video outputs."
    )


def test_audio_batch_conversion_avoids_output_name_collisions(
    tmp_workspace, monkeypatch
):
    """Ensures audio batch conversion creates distinct outputs for matching stems."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "track.wav").write_bytes(b"wav source")
    (in_dir / "track.flac").write_bytes(b"flac source")

    def fake_converter(
        input_path, output_path, target_format, cancel_event=None, **_kwargs
    ):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(input_path.read_bytes())
        return True

    monkeypatch.setattr(audio_conversion, "file_converter", fake_converter)

    stats = audio_conversion.directory_converter(in_dir, out_dir, target_format="mp3")

    outputs = list((out_dir / "converted").glob("*.mp3"))

    assert stats["success"] == 2, (
        "[batch] Both same-stem audio tracks must convert without overwriting each other."
    )
    assert stats["failed"] == 0, (
        "[batch] Expected 0 failures during audio stem-collision conversion."
    )
    assert len(outputs) == 2, (
        "[batch] Destination folder must contain 2 separate MP3 files rather than overwriting one."
    )
    assert len({path.name for path in outputs}) == 2, (
        "[batch] Output filenames for same-stem audio files must be deduplicated."
    )
    assert {path.read_bytes() for path in outputs} == {
        b"wav source",
        b"flac source",
    }, (
        "[batch] Both audio source payloads must be preserved independently without data loss."
    )
    assert stats["compressed_bytes"] == sum(path.stat().st_size for path in outputs), (
        "[batch] compressed_bytes statistic must sum the sizes of all distinct audio outputs."
    )


def test_image_batch_conversion_preserves_existing_output(tmp_workspace, monkeypatch):
    """Ensures image batch conversion does not overwrite an existing destination."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "photo.png").write_bytes(b"png source")

    previous_session = out_dir / "converted"
    previous_session.mkdir(parents=True)

    existing_output = previous_session / "photo_converted.webp"
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
    assert len(list(out_dir.rglob("*.webp"))) == 2, (
        "[batch] Both the pre-existing WebP and newly converted WebP must exist across sessions."
    )
