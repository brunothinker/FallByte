"""Core: testes PARAMETRIZADOS entre varios directory processors (nao dividir)."""

import pytest

from src.audio import (
    audio_directory_compression as audio_compression,
)
from src.audio import (
    audio_directory_conversion as audio_conversion,
)
from src.image import (
    image_directory_compression as image_compression,
)
from src.image import (
    image_directory_conversion as image_conversion,
)
from src.video import (
    video_directory_compression as video_compression,
)
from src.video import (
    video_directory_conversion as video_conversion,
)

# (module, scanner attr, file processor attr, session folder name, kwargs)
PROCESSORS = [
    pytest.param(
        image_compression,
        "scan_image_files",
        "file_compressor",
        "compressed",
        {"quality": 80},
        id="image-compression",
    ),
    pytest.param(
        image_conversion,
        "scan_image_files",
        "file_converter",
        "converted",
        {"target_format": "webp"},
        id="image-conversion",
    ),
    pytest.param(
        video_compression,
        "scan_video_files",
        "file_compressor",
        "compressed",
        {"quality": 80},
        id="video-compression",
    ),
    pytest.param(
        video_conversion,
        "scan_video_files",
        "file_converter",
        "converted",
        {"target_format": "mp4"},
        id="video-conversion",
    ),
    pytest.param(
        audio_compression,
        "scan_audio_files",
        "file_compressor",
        "compressed",
        {"quality": 80},
        id="audio-compression",
    ),
    pytest.param(
        audio_conversion,
        "scan_audio_files",
        "file_converter",
        "converted",
        {"target_format": "mp3"},
        id="audio-conversion",
    ),
]


def _run_directory_processor(module, input_dir, output_dir, operation_kwargs) -> dict:
    """Runs the converter or compressor orchestrator of a module.

    Args:
        module: Orchestrator module exposing `directory_converter` or
            `directory_compressor`.
        input_dir (Path): Source directory.
        output_dir (Path): Destination root directory.
        operation_kwargs (dict): Operation-specific keyword arguments.

    Returns:
        dict: Statistics dictionary returned by the orchestrator.
    """
    if "conversion" in module.__name__:
        return module.directory_converter(input_dir, output_dir, **operation_kwargs)
    return module.directory_compressor(input_dir, output_dir, **operation_kwargs)


@pytest.mark.parametrize(
    "module,scanner_name,processor_name,folder_name,operation_kwargs",
    PROCESSORS,
)
def test_directory_processor_creates_separate_session_folder(
    tmp_path,
    monkeypatch,
    module,
    scanner_name,
    processor_name,
    folder_name,
    operation_kwargs,
):
    """Each run writes to its own session folder and never touches previous runs."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    if "image" in module.__name__:
        extension = ".png"
    elif "video" in module.__name__:
        extension = ".mp4"
    else:
        extension = ".mp3"

    source = input_dir / f"sample{extension}"
    source.write_bytes(b"source data")

    monkeypatch.setattr(module, scanner_name, lambda _input_dir: [source])

    def fake_processor(input_path, output_path, **_kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(input_path.read_bytes())
        return True

    monkeypatch.setattr(module, processor_name, fake_processor)

    stats = _run_directory_processor(module, input_dir, output_dir, operation_kwargs)

    session_dir = output_dir / folder_name

    assert stats["success"] == 1, (
        f"[batch] Expected first batch run for '{module.__name__}' to report 1 success."
    )
    assert stats["failed"] == 0, (
        f"[batch] Expected first batch run for '{module.__name__}' to report 0 failures."
    )
    assert session_dir.is_dir(), (
        f"[batch] Expected first batch run to create session directory '{session_dir}'."
    )

    outputs = list(session_dir.rglob("*"))
    assert any(path.is_file() for path in outputs), (
        f"[batch] Expected processed output file inside '{session_dir}'."
    )
    produced = [path for path in outputs if path.is_file()]
    assert {path.stem for path in produced} == {"sample"}, (
        f"[batch] Batch output of '{module.__name__}' must keep the original file stem."
    )

    # A second run must use a new folder and preserve the first result.
    first_files = [path for path in session_dir.rglob("*") if path.is_file()]
    first_contents = {
        path.relative_to(session_dir): path.read_bytes() for path in first_files
    }

    second_stats = _run_directory_processor(
        module, input_dir, output_dir, operation_kwargs
    )

    second_session_dir = output_dir / f"{folder_name}_1"

    assert second_stats["success"] == 1, (
        f"[batch] Expected second batch run for '{module.__name__}' to report 1 success."
    )
    assert second_session_dir.is_dir(), (
        f"[batch] Expected second batch run to isolate outputs into '{second_session_dir}'."
    )

    assert all(
        (session_dir / relative_path).read_bytes() == content
        for relative_path, content in first_contents.items()
    ), (
        "[batch] Second batch run mutated or overwrote files belonging to the first session."
    )


@pytest.mark.parametrize(
    "module,scanner_name,processor_name,folder_name,operation_kwargs",
    PROCESSORS,
)
def test_directory_processor_does_not_create_session_folder_without_valid_files(
    tmp_path,
    monkeypatch,
    module,
    scanner_name,
    processor_name,
    folder_name,
    operation_kwargs,
):
    """No session folder is created, and no file is processed, for empty inputs."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    monkeypatch.setattr(module, scanner_name, lambda _input_dir: [])

    def unexpected_processor(*_args, **_kwargs):
        pytest.fail("The file processor must not run when there are no valid files")

    monkeypatch.setattr(module, processor_name, unexpected_processor)

    stats = _run_directory_processor(module, input_dir, output_dir, operation_kwargs)

    assert stats["success"] == 0, (
        "[batch] Empty directory batch run must report 0 successes."
    )
    assert stats["failed"] == 0, (
        "[batch] Empty directory batch run must report 0 failures."
    )
    assert not (output_dir / folder_name).exists(), (
        f"[batch] Empty directory batch run must not create an empty '{folder_name}' session folder."
    )
    assert list(output_dir.iterdir()) == [], (
        "[batch] Empty directory batch run must leave the destination directory completely untouched."
    )
