"""Batch orchestration tests: session folders, name collisions and cancel cleanup.

Covers the directory orchestrators of the four engines (image/video x
conversion/compression) using fake file processors, the generic `run_batch`
statistics contract, plus the shared helpers `create_unique_output_dir` and
`safe_cleanup_session_files`.
"""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.image import image_directory_compression as image_compression
from src.image import image_directory_conversion as image_conversion
from src.utils.batch_runner import run_batch
from src.utils.cleanup import safe_cleanup_session_files
from src.utils.output_directory import create_unique_output_dir
from src.video import video_directory_compression as video_compression
from src.video import video_directory_conversion as video_conversion

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


# --- Unique session directories ---


def test_create_unique_output_dir_uses_base_name_first(tmp_path):
    """Uses the plain folder name when it is still free."""
    result = create_unique_output_dir(tmp_path, "compressed")

    assert result == tmp_path / "compressed"
    assert result.is_dir()


def test_create_unique_output_dir_uses_first_available_suffix(tmp_path):
    """Picks the first free numeric suffix and leaves existing folders untouched."""
    for name in ("compressed", "compressed_1", "compressed_3"):
        (tmp_path / name).mkdir()

    result = create_unique_output_dir(tmp_path, "compressed")

    assert result == tmp_path / "compressed_2"
    assert result.is_dir()
    assert (tmp_path / "compressed").is_dir()
    assert (tmp_path / "compressed_1").is_dir()
    assert (tmp_path / "compressed_3").is_dir()


def test_create_unique_output_dir_creates_missing_parent(tmp_path):
    """Creates the missing parent directories together with the session folder."""
    parent = tmp_path / "nested" / "destination"

    result = create_unique_output_dir(parent, "converted")

    assert result == parent / "converted"
    assert result.is_dir()


def test_create_unique_output_dir_is_safe_for_concurrent_calls(tmp_path):
    """Guarantees distinct folders when called from several threads at once."""

    def create_folder(_):
        return create_unique_output_dir(tmp_path, "converted")

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(create_folder, range(8)))

    assert len(set(results)) == 8
    assert all(path.is_dir() for path in results)
    assert {path.name for path in results} == {
        "converted",
        *(f"converted_{index}" for index in range(1, 8)),
    }


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

    extension = ".png" if "image" in module.__name__ else ".mp4"
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

    assert stats["success"] == 1
    assert stats["failed"] == 0
    assert session_dir.is_dir()

    outputs = list(session_dir.rglob("*"))
    assert any(path.is_file() for path in outputs)

    # A second run must use a new folder and preserve the first result.
    first_files = [path for path in session_dir.rglob("*") if path.is_file()]
    first_contents = {
        path.relative_to(session_dir): path.read_bytes() for path in first_files
    }

    second_stats = _run_directory_processor(
        module, input_dir, output_dir, operation_kwargs
    )

    second_session_dir = output_dir / f"{folder_name}_1"

    assert second_stats["success"] == 1
    assert second_session_dir.is_dir()

    assert all(
        (session_dir / relative_path).read_bytes() == content
        for relative_path, content in first_contents.items()
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
        pytest.fail(
            "The file processor must not run when there are no valid files"
        )

    monkeypatch.setattr(module, processor_name, unexpected_processor)

    stats = _run_directory_processor(module, input_dir, output_dir, operation_kwargs)

    assert stats["success"] == 0
    assert stats["failed"] == 0
    assert not (output_dir / folder_name).exists()
    assert list(output_dir.iterdir()) == []


# --- run_batch statistics contract ---


def test_run_batch_reports_total_files(tmp_path):
    """run_batch must report the number of scanned files, failed ones included.

    Controllers build their summary message ("X of Y") from `total_files`, and
    the controller tests use fake engines that always provide it, so this is
    the only test guarding the real `run_batch` output.
    """
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    for name in ("a.png", "b.png", "c.png"):
        (input_dir / name).write_bytes(b"x")

    def process(src_file, dst_file):
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        dst_file.write_bytes(b"x")
        return src_file.name != "c.png"  # c.png is reported as a failure

    stats = run_batch(
        input_dir=input_dir,
        output_dir=tmp_path / "out",
        session_name="compressed",
        scanner=lambda path: sorted(path.glob("*.png")),
        process_file=process,
        build_destination=lambda src_file, session_dir: session_dir / src_file.name,
    )

    assert stats["total_files"] == 3
    assert stats["success"] == 2
    assert stats["failed"] == 1
    assert stats["success"] + stats["failed"] == stats["total_files"]
    assert "no_files" not in stats


def test_run_batch_reports_zero_total_files_when_nothing_to_process(tmp_path):
    """An empty scan reports total_files == 0 together with the no_files flag."""
    stats = run_batch(
        input_dir=tmp_path,
        output_dir=tmp_path / "out",
        session_name="compressed",
        scanner=lambda path: [],
        process_file=lambda src_file, dst_file: True,
        build_destination=lambda src_file, session_dir: session_dir / src_file.name,
    )

    assert stats["total_files"] == 0
    assert stats["no_files"] is True
    assert not (tmp_path / "out").exists()


def test_run_batch_handles_unexpected_exception(tmp_path):
    """Ensures run_batch handles unexpected inner exceptions cleanly without session cleanup."""
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    (input_dir / "sample.png").write_bytes(b"data")

    def process_with_error(src_file, dst_file):
        raise RuntimeError("Unexpected engine crash")

    stats = run_batch(
        input_dir=input_dir,
        output_dir=tmp_path / "out",
        session_name="compressed",
        scanner=lambda path: sorted(path.glob("*.png")),
        process_file=process_with_error,
        build_destination=lambda src_file, session_dir: session_dir / src_file.name,
    )

    assert stats["cancelled"] is False
    assert stats["total_files"] == 1
    assert stats["success"] == 0
    assert stats["failed"] == 0


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

    assert stats["cancelled"] is True
    assert list(out_dir.iterdir()) == []


# --- Batch conversion output naming ---


def test_image_batch_conversion_avoids_output_name_collisions(
    tmp_workspace, monkeypatch
):
    """Ensures image batch conversion creates distinct outputs for matching stems."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "photo.png").write_bytes(b"png source")
    (in_dir / "photo.jpg").write_bytes(b"jpg source")

    def fake_converter(
        input_path, output_path, target_format, transparency_replacement_color, **_kwargs
    ):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(input_path.read_bytes())
        return True

    monkeypatch.setattr(
        image_conversion, "file_converter", fake_converter
    )

    stats = image_conversion.directory_converter(
        in_dir, out_dir, target_format="webp"
    )

    outputs = list((out_dir / "converted").glob("*.webp"))

    assert stats["success"] == 2
    assert stats["failed"] == 0
    assert len(outputs) == 2
    assert len({path.name for path in outputs}) == 2
    assert {path.read_bytes() for path in outputs} == {
        b"png source",
        b"jpg source",
    }
    assert stats["compressed_bytes"] == sum(
        path.stat().st_size for path in outputs
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

    monkeypatch.setattr(
        video_conversion, "file_converter", fake_converter
    )

    stats = video_conversion.directory_converter(
        in_dir, out_dir, target_format="mp4"
    )

    outputs = list((out_dir / "converted").glob("*.mp4"))

    assert stats["success"] == 2
    assert stats["failed"] == 0
    assert len(outputs) == 2
    assert len({path.name for path in outputs}) == 2
    assert {path.read_bytes() for path in outputs} == {
        b"avi source",
        b"mov source",
    }
    assert stats["compressed_bytes"] == sum(
        path.stat().st_size for path in outputs
    )


def test_image_batch_conversion_preserves_existing_output(
    tmp_workspace, monkeypatch
):
    """Ensures image batch conversion does not overwrite an existing destination."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "photo.png").write_bytes(b"png source")

    previous_session = out_dir / "converted"
    previous_session.mkdir(parents=True)

    existing_output = previous_session / "photo_converted.webp"
    existing_output.write_bytes(b"existing user data")

    def fake_converter(
        input_path, output_path, target_format, transparency_replacement_color, **_kwargs
    ):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(input_path.read_bytes())
        return True

    monkeypatch.setattr(
        image_conversion, "file_converter", fake_converter
    )

    stats = image_conversion.directory_converter(
        in_dir, out_dir, target_format="webp"
    )

    assert stats["success"] == 1
    assert existing_output.read_bytes() == b"existing user data"

    new_session = out_dir / "converted_1"
    assert new_session.is_dir()
    assert len(list(out_dir.rglob("*.webp"))) == 2


# --- Cancellation & cleanup ---


def test_video_batch_conversion_cleans_up_when_cancelled(
    tmp_workspace, monkeypatch
):
    """Ensures an interruption inside the file processor triggers session cleanup."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "a_clip.avi").write_bytes(b"first source")
    (in_dir / "b_clip.mov").write_bytes(b"second source")

    def fake_converter(
        input_path, output_path, target_format, cancel_event=None, **_kwargs
    ):
        if input_path.name == "b_clip.mov":
            raise InterruptedError("CANCELLED_BY_USER")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(input_path.read_bytes())
        return True

    monkeypatch.setattr(
        video_conversion, "file_converter", fake_converter
    )

    stats = video_conversion.directory_converter(
        in_dir, out_dir, target_format="mp4", cancel_event=threading.Event()
    )

    assert stats["cancelled"] is True
    assert stats["cleaned_files_count"] == 1
    assert not (out_dir / "converted").exists()


def test_video_batch_compression_removes_empty_session_folder_when_cancelled(
    tmp_workspace, monkeypatch
):
    """Ensures cancelling a compression batch leaves no empty session folder behind."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "clip.mp4").write_bytes(b"source")

    def fake_compressor(
        input_path, output_path, quality, cancel_event=None, **_kwargs
    ):
        raise InterruptedError("CANCELLED_BY_USER")

    monkeypatch.setattr(
        video_compression, "file_compressor", fake_compressor
    )

    stats = video_compression.directory_compressor(
        in_dir, out_dir, quality=80, cancel_event=threading.Event()
    )

    assert stats["cancelled"] is True
    assert list(out_dir.iterdir()) == []


def test_safe_cleanup_preserves_user_files(tmp_workspace):
    """Verifies that session cleanup removes temporary files without touching user files."""
    _, out_dir = tmp_workspace

    user_file = out_dir / "important_user_doc.txt"
    user_file.write_text("user data")

    session_file = out_dir / "subfolder" / "temp_output.png"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text("temporary image data")

    cleaned_count = safe_cleanup_session_files(
        [session_file], root_output_dir=out_dir
    )

    assert cleaned_count == 1
    assert not session_file.exists()
    assert user_file.exists()
    assert user_file.read_text() == "user data"


def test_safe_cleanup_preserves_pre_existing_files(tmp_workspace):
    """Verifies that safe_cleanup_session_files does not delete pre-existing files."""
    _, out_dir = tmp_workspace

    existing_file = out_dir / "pre_existing_output.mp4"
    existing_file.write_text("original user data")

    cleaned_count = safe_cleanup_session_files(
        created_files=[existing_file],
        root_output_dir=out_dir,
        pre_existing_files=[existing_file],
    )

    assert cleaned_count == 0
    assert existing_file.exists()
    assert existing_file.read_text() == "original user data"


def test_run_batch_cleans_up_without_deleting_pre_existing_files(tmp_workspace):
    """Ensures batch cancellation preserves pre-existing files that were overwritten."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "file1.png").write_bytes(b"source 1")
    (in_dir / "file2.png").write_bytes(b"source 2")

    session_dir = out_dir / "compressed"
    session_dir.mkdir(parents=True, exist_ok=True)

    pre_existing_file = session_dir / "file1.png"
    pre_existing_file.write_bytes(b"pre-existing data")

    def process_with_cancel(src_file, dst_file):
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        dst_file.write_bytes(b"new data")
        if src_file.name == "file2.png":
            raise InterruptedError("CANCELLED")
        return True

    stats = run_batch(
        input_dir=in_dir,
        output_dir=out_dir,
        session_name="compressed",
        scanner=lambda p: sorted(p.glob("*.png")),
        process_file=process_with_cancel,
        build_destination=lambda src, s_dir: session_dir / src.name,
    )

    assert stats["cancelled"] is True
    assert pre_existing_file.exists()
    assert pre_existing_file.read_bytes() == b"new data"