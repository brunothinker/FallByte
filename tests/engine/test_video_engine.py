"""Video engine tests: FFmpeg-backed conversion, compression and process control.

Covers per-container conversion, quality levels, unusual/invalid inputs
(Unicode paths, missing and corrupted files) and the cancellation lifecycle of
FFmpeg processes (`run_strategies`, pre-set cancel events and the exit hook).
Requires the bundled FFmpeg binary.
"""

import subprocess
import threading
import time

import pytest

from src.image.conversion.image_file_conversion import file_converter
from src.video.compression.video_file_compression import file_compressor as video_compressor
from src.video.conversion.video_file_conversion import file_converter as video_converter
from src.video.utils import ffmpeg_utils
from src.video.utils.binary_manager import get_ffmpeg_path


def _long_encode_command(output_file) -> list[str]:
    """Builds a deliberately slow FFmpeg command used to test cancellation.

    Args:
        output_file (Path): Destination file the command would write.

    Returns:
        list[str]: Command line encoding a 10-minute synthetic video with the
            `veryslow` preset, which never finishes within the test timeout.
    """
    return [
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


# --- Conversion & compression ---


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


# --- Advanced I/O & edge cases ---


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


# --- Cancellation & process lifecycle ---


def test_run_strategies_terminates_running_ffmpeg(tmp_path, monkeypatch):
    """Verifies that setting the cancel event stops FFmpeg quickly and removes partial output."""
    output_file = tmp_path / "long_encode.mp4"
    cmd = _long_encode_command(output_file)

    # Record every spawned process so we can assert it was really terminated.
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


def test_terminate_active_processes_kills_ffmpeg_and_removes_output(tmp_path):
    """Verifies the exit hook kills running FFmpeg processes and deletes partial output."""
    output_file = tmp_path / "long_encode.mp4"
    cmd = _long_encode_command(output_file)

    worker = threading.Thread(
        target=ffmpeg_utils.run_strategies,
        args=([("long encode", cmd)], output_file, "long_encode.mp4"),
        daemon=True,
    )
    worker.start()

    # Wait until the process is registered in the active-process registry.
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
