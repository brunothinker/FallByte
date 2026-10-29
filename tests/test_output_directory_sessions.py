from concurrent.futures import ThreadPoolExecutor

import pytest

from src.image.compression import image_directory_compression as image_compression
from src.image.conversion import image_directory_conversion as image_conversion
from src.utils.output_directory import create_unique_output_dir
from src.video.compression import video_directory_compression as video_compression
from src.video.conversion import video_directory_conversion as video_conversion

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


def test_create_unique_output_dir_uses_base_name_first(tmp_path):
    result = create_unique_output_dir(tmp_path, "compressed")

    assert result == tmp_path / "compressed"
    assert result.is_dir()


def test_create_unique_output_dir_uses_first_available_suffix(tmp_path):
    for name in ("compressed", "compressed_1", "compressed_3"):
        (tmp_path / name).mkdir()

    result = create_unique_output_dir(tmp_path, "compressed")

    assert result == tmp_path / "compressed_2"
    assert result.is_dir()
    assert (tmp_path / "compressed").is_dir()
    assert (tmp_path / "compressed_1").is_dir()
    assert (tmp_path / "compressed_3").is_dir()


def test_create_unique_output_dir_creates_missing_parent(tmp_path):
    parent = tmp_path / "nested" / "destination"

    result = create_unique_output_dir(parent, "converted")

    assert result == parent / "converted"
    assert result.is_dir()


def test_create_unique_output_dir_is_safe_for_concurrent_calls(tmp_path):
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

    if "conversion" in module.__name__:
        stats = module.directory_converter(
            input_dir, output_dir, **operation_kwargs
        )
    else:
        stats = module.directory_compressor(
            input_dir, output_dir, **operation_kwargs
        )

    session_dir = output_dir / folder_name

    assert stats["success"] == 1
    assert stats["failed"] == 0
    assert session_dir.is_dir()

    outputs = list(session_dir.rglob("*"))
    assert any(path.is_file() for path in outputs)

    # A second run must use a new folder and preserve the first result.
    first_files = [
        path for path in session_dir.rglob("*") if path.is_file()
    ]
    first_contents = {
        path.relative_to(session_dir): path.read_bytes()
        for path in first_files
    }

    if "conversion" in module.__name__:
        second_stats = module.directory_converter(
            input_dir, output_dir, **operation_kwargs
        )
    else:
        second_stats = module.directory_compressor(
            input_dir, output_dir, **operation_kwargs
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

    if "conversion" in module.__name__:
        stats = module.directory_converter(
            input_dir, output_dir, **operation_kwargs
        )
    else:
        stats = module.directory_compressor(
            input_dir, output_dir, **operation_kwargs
        )

    assert stats["success"] == 0
    assert stats["failed"] == 0
    assert not (output_dir / folder_name).exists()
    assert list(output_dir.iterdir()) == []