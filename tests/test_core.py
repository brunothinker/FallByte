import subprocess
import threading
import time

import pytest
from PIL import Image

from src.image.compression.file_compression import file_compressor
from src.image.conversion import directory_conversion as image_directory_conversion
from src.image.conversion.file_conversion import file_converter
from src.image.utils.image_cleanup import safe_cleanup_session_files
from src.video.compression import directory_compression as video_directory_compression
from src.video.compression.file_compression import file_compressor as video_compressor
from src.video.conversion import directory_conversion as video_directory_conversion
from src.video.conversion.file_conversion import file_converter as video_converter
from src.video.utils import ffmpeg_utils
from src.video.utils.binary_manager import get_ffmpeg_path

IMAGE_TARGET_FORMATS = ["JPEG", "PNG", "WEBP", "BMP", "ICO", "TIFF"]


# --- IMAGE ENGINE TESTS ---

@pytest.mark.parametrize("source_mode", ["RGB", "RGBA", "P", "CMYK"])
@pytest.mark.parametrize("target_fmt", IMAGE_TARGET_FORMATS)
def test_image_conversion_matrix(
    tmp_workspace, create_sample_image, source_mode, target_fmt
):
    """Tests full image format and color mode conversion matrix."""
    in_dir, out_dir = tmp_workspace
    ext = "jpg" if target_fmt == "JPEG" else target_fmt.lower()

    src_fmt = "TIFF" if source_mode == "CMYK" else "PNG"
    src_ext = "tiff" if source_mode == "CMYK" else "png"

    src_img = in_dir / f"sample_{source_mode}.{src_ext}"
    if not src_img.exists():
        create_sample_image(src_img, mode=source_mode, fmt=src_fmt)

    dst_path = out_dir / f"converted_{source_mode}_to_{target_fmt.lower()}.{ext}"

    success = file_converter(
        src_img,
        dst_path,
        target_format=target_fmt,
        transparency_replacement_color="#FFFFFF",
    )

    assert success is True
    assert dst_path.exists()
    assert dst_path.stat().st_size > 0


def test_ico_sizing_clamp(tmp_workspace, create_sample_image):
    """Verifies that ICO conversion clamps dimensions to maximum allowable 256x256."""
    in_dir, out_dir = tmp_workspace
    large_png = in_dir / "large.png"
    create_sample_image(large_png, mode="RGBA", size=(500, 500), fmt="PNG")

    dst_ico = out_dir / "icon.ico"
    success = file_converter(large_png, dst_ico, target_format="ICO")

    assert success is True
    assert dst_ico.exists()

    with Image.open(dst_ico) as img:
        assert img.size[0] <= 256
        assert img.size[1] <= 256


def test_image_compression_keep_original_when_uncompressible(
    tmp_workspace, create_sample_image
):
    """Ensures image compression fallback handles formats without compression gains cleanly."""
    in_dir, out_dir = tmp_workspace
    src_gif = in_dir / "sample.gif"
    create_sample_image(src_gif, mode="P", fmt="GIF")

    dst_gif = out_dir / "compressed.gif"
    success = file_compressor(src_gif, dst_gif, quality=80)

    assert success is True
    assert dst_gif.exists()


# --- VIDEO ENGINE TESTS ---

@pytest.mark.parametrize("target_format", ["mkv", "avi", "mov", "webm", "mp4"])
def test_video_conversion_all_formats(
    tmp_workspace, create_sample_video, target_format
):
    """Tests video conversion across all supported container formats."""
    in_dir, out_dir = tmp_workspace
    src_mp4 = create_sample_video(in_dir / "input.mp4", duration_sec=1)

    dst_file = out_dir / f"output.{target_format}"
    success = video_converter(
        src_mp4, dst_file, target_format=target_format
    )

    assert success is True
    assert dst_file.exists()
    assert dst_file.stat().st_size > 0


@pytest.mark.parametrize("quality", [30, 60, 80])
def test_video_compression_levels(tmp_workspace, create_sample_video, quality):
    """Tests video compression across multiple quality levels."""
    in_dir, out_dir = tmp_workspace
    src_mp4 = create_sample_video(in_dir / "input.mp4", duration_sec=1)

    dst_mp4 = out_dir / f"compressed_q{quality}.mp4"
    success = video_compressor(src_mp4, dst_mp4, quality=quality)

    assert success is True
    assert dst_mp4.exists()
    assert dst_mp4.stat().st_size > 0


# --- BATCH CONVERSION TESTS ---

def test_image_batch_conversion_avoids_output_name_collisions(
    tmp_workspace, monkeypatch
):
    """Ensures image batch conversion creates distinct outputs for matching stems."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "photo.png").write_bytes(b"png source")
    (in_dir / "photo.jpg").write_bytes(b"jpg source")

    def fake_converter(
        input_path, output_path, target_format, transparency_replacement_color
    ):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(input_path.read_bytes())
        return True

    monkeypatch.setattr(
        image_directory_conversion, "file_converter", fake_converter
    )

    stats = image_directory_conversion.directory_converter(
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

    def fake_converter(input_path, output_path, target_format, cancel_event=None):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(input_path.read_bytes())
        return True

    monkeypatch.setattr(
        video_directory_conversion, "file_converter", fake_converter
    )

    stats = video_directory_conversion.directory_converter(
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
        input_path, output_path, target_format, transparency_replacement_color
    ):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(input_path.read_bytes())
        return True

    monkeypatch.setattr(
        image_directory_conversion, "file_converter", fake_converter
    )

    stats = image_directory_conversion.directory_converter(
        in_dir, out_dir, target_format="webp"
    )

    assert stats["success"] == 1
    assert existing_output.read_bytes() == b"existing user data"

    new_session = out_dir / "converted_1"
    assert new_session.is_dir()
    assert len(list(out_dir.rglob("*.webp"))) == 2


# --- ADVANCED I/O & EDGE CASES (CASE 1) ---

def test_process_files_with_special_characters_and_spaces(
    tmp_workspace, create_sample_video, create_sample_image
):
    """Ensures file processors handle paths with Unicode characters, spaces, and symbols."""
    in_dir, out_dir = tmp_workspace

    special_folder = in_dir / "Vídeos & Imagens de Teste (2026) #1"
    special_folder.mkdir(parents=True, exist_ok=True)

    special_video = special_folder / "vídeo de teste 100%_ok.mp4"
    special_image = special_folder / "imagem com acentuação & espaço.png"

    create_sample_video(special_video, duration_sec=1)
    create_sample_image(special_image, mode="RGB", fmt="PNG")

    out_video = out_dir / "vídeo_convertido_output.mkv"
    out_image = out_dir / "imagem_convertida_output.jpg"

    video_success = video_converter(
        special_video, out_video, target_format="mkv"
    )
    image_success = file_converter(
        special_image, out_image, target_format="JPEG"
    )

    assert video_success is True
    assert out_video.exists()
    assert image_success is True
    assert out_image.exists()


def test_process_non_existent_file_handling(tmp_path):
    """Verifies that non-existent input paths return False or handle errors gracefully."""
    fake_input = tmp_path / "ghost_file.mp4"
    fake_output = tmp_path / "output.mp4"

    video_success = video_converter(
        fake_input, fake_output, target_format="mp4"
    )

    assert video_success is False
    assert not fake_output.exists()


def test_process_corrupted_media_file_handling(tmp_path):
    """Verifies that corrupted media files are handled without crashing the runner."""
    corrupted_file = tmp_path / "corrupted_media.mp4"
    corrupted_file.write_bytes(b"NOT_A_VALID_MEDIA_HEADER")

    output_file = tmp_path / "failed_output.mp4"

    video_success = video_converter(
        corrupted_file, output_file, target_format="mp4"
    )

    assert video_success is False
    assert not output_file.exists()


# --- VIDEO CANCELLATION TESTS ---

def test_run_strategies_terminates_running_ffmpeg(tmp_path, monkeypatch):
    """Verifies that setting the cancel event stops FFmpeg quickly and removes partial output."""
    output_file = tmp_path / "long_encode.mp4"
    cmd = [
        str(get_ffmpeg_path()),
        "-hide_banner",
        "-nostdin",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=600:size=1280x720:rate=30",
        "-c:v",
        "libx264",
        "-preset",
        "veryslow",
        str(output_file),
    ]

    spawned: list[subprocess.Popen] = []
    original_popen = subprocess.Popen

    def recording_popen(*args, **kwargs):
        process = original_popen(*args, **kwargs)
        spawned.append(process)
        return process

    monkeypatch.setattr(ffmpeg_utils.subprocess, "Popen", recording_popen)

    cancel_event = threading.Event()
    timer = threading.Timer(1.0, cancel_event.set)
    timer.start()

    start = time.perf_counter()
    try:
        with pytest.raises(InterruptedError):
            ffmpeg_utils.run_strategies(
                [("long encode", cmd)], output_file, "long_encode.mp4", cancel_event
            )
    finally:
        timer.cancel()
    elapsed = time.perf_counter() - start

    assert elapsed < 10
    assert len(spawned) == 1
    assert spawned[0].poll() is not None
    assert not output_file.exists()


def test_video_converter_raises_when_cancelled(tmp_workspace, create_sample_video):
    """Ensures a pre-set cancel event raises InterruptedError and leaves no output."""
    in_dir, out_dir = tmp_workspace
    src_mp4 = create_sample_video(in_dir / "input.mp4", duration_sec=1)
    dst_file = out_dir / "output.avi"

    cancel_event = threading.Event()
    cancel_event.set()

    with pytest.raises(InterruptedError):
        video_converter(
            src_mp4, dst_file, target_format="avi", cancel_event=cancel_event
        )

    assert not dst_file.exists()


def test_video_compressor_raises_when_cancelled(tmp_workspace, create_sample_video):
    """Ensures a pre-set cancel event raises InterruptedError and leaves no output."""
    in_dir, out_dir = tmp_workspace
    src_mp4 = create_sample_video(in_dir / "input.mp4", duration_sec=1)
    dst_file = out_dir / "compressed.mp4"

    cancel_event = threading.Event()
    cancel_event.set()

    with pytest.raises(InterruptedError):
        video_compressor(
            src_mp4, dst_file, quality=60, cancel_event=cancel_event
        )

    assert not dst_file.exists()


def test_video_batch_conversion_cleans_up_when_cancelled(
    tmp_workspace, monkeypatch
):
    """Ensures an interruption inside the file processor triggers session cleanup."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "a_clip.avi").write_bytes(b"first source")
    (in_dir / "b_clip.mov").write_bytes(b"second source")

    def fake_converter(input_path, output_path, target_format, cancel_event=None):
        if input_path.name == "b_clip.mov":
            raise InterruptedError("CANCELLED_BY_USER")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(input_path.read_bytes())
        return True

    monkeypatch.setattr(
        video_directory_conversion, "file_converter", fake_converter
    )

    stats = video_directory_conversion.directory_converter(
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

    def fake_compressor(input_path, output_path, quality, cancel_event=None):
        raise InterruptedError("CANCELLED_BY_USER")

    monkeypatch.setattr(
        video_directory_compression, "file_compressor", fake_compressor
    )

    stats = video_directory_compression.directory_compressor(
        in_dir, out_dir, quality=80, cancel_event=threading.Event()
    )

    assert stats["cancelled"] is True
    assert list(out_dir.iterdir()) == []


def test_terminate_active_processes_kills_ffmpeg_and_removes_output(tmp_path):
    """Verifies the exit hook kills running FFmpeg processes and deletes partial output."""
    output_file = tmp_path / "long_encode.mp4"
    cmd = [
        str(get_ffmpeg_path()),
        "-hide_banner",
        "-nostdin",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=600:size=1280x720:rate=30",
        "-c:v",
        "libx264",
        "-preset",
        "veryslow",
        str(output_file),
    ]

    worker = threading.Thread(
        target=ffmpeg_utils.run_strategies,
        args=([("long encode", cmd)], output_file, "long_encode.mp4"),
        daemon=True,
    )
    worker.start()

    deadline = time.perf_counter() + 5
    while not ffmpeg_utils._active_processes and time.perf_counter() < deadline:
        time.sleep(0.05)

    registered = list(ffmpeg_utils._active_processes)
    assert len(registered) == 1

    ffmpeg_utils.terminate_active_processes()
    worker.join(timeout=10)

    assert not worker.is_alive()
    assert registered[0].poll() is not None
    assert not output_file.exists()
    assert not ffmpeg_utils._active_processes


# --- CLEANUP TESTS ---

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