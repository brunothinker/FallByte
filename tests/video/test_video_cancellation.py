"""Tests for FFmpeg process termination, cancellation events, and active-process cleanup."""

import subprocess
import threading
import time

import pytest

from src.utils.binary_manager import get_ffmpeg_path
from src.video.utils import video_ffmpeg_utils
from src.video.video_file_compression import file_compressor as video_compressor
from src.video.video_file_conversion import file_converter as video_converter


def _long_encode_command(output_file) -> list[str]:
    """Builds a deliberately slow FFmpeg command used to test cancellation.

    Args:
        output_file (Path): Destination file the command would write.

    Returns:
        list[str]: Command line encoding a 10-minute synthetic video with the
            `veryslow` preset, which never finishes within the test timeout.
    """
    try:
        ffmpeg_bin = get_ffmpeg_path()
    except (FileNotFoundError, OSError) as err:
        pytest.skip(f"FFmpeg binary not available: {err}")

    return [
        str(ffmpeg_bin),
        "-hide_banner",
        "-nostdin",
        "-progress",
        "pipe:1",
        "-nostats",
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

    monkeypatch.setattr(video_ffmpeg_utils.subprocess, "Popen", recording_popen)

    cancel_event = threading.Event()
    timer = threading.Timer(1.0, cancel_event.set)
    timer.start()

    start = time.perf_counter()
    try:
        with pytest.raises(InterruptedError):
            video_ffmpeg_utils.run_strategies(
                [("long encode", cmd)], output_file, "long_encode.mp4", cancel_event
            )
    finally:
        timer.cancel()
    elapsed = time.perf_counter() - start

    assert elapsed < 10, (
        f"[video] Cancelled FFmpeg encode took too long ({elapsed:.2f}s) instead of aborting promptly."
    )
    assert len(spawned) == 1, (
        f"[video] Expected exactly 1 FFmpeg subprocess to be spawned before cancellation, got {len(spawned)}."
    )
    assert spawned[0].poll() is not None, (
        "[video] Spawned FFmpeg process was left running as an orphan after cancel_event fired."
    )
    assert not output_file.exists(), (
        "[video] Partial output file must be unlinked when FFmpeg is cancelled mid-encode."
    )


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

    assert not dst_file.exists(), (
        "[video] Pre-cancelled video conversion must not produce an output file."
    )


def test_video_compressor_raises_when_cancelled(tmp_workspace, create_sample_video):
    """Ensures a pre-set cancel event raises InterruptedError and leaves no output."""
    in_dir, out_dir = tmp_workspace
    src_mp4 = create_sample_video(in_dir / "input.mp4", duration_sec=1)
    dst_file = out_dir / "compressed.mp4"

    cancel_event = threading.Event()
    cancel_event.set()

    with pytest.raises(InterruptedError):
        video_compressor(src_mp4, dst_file, quality=60, cancel_event=cancel_event)

    assert not dst_file.exists(), (
        "[video] Pre-cancelled video compression must not produce an output file."
    )


def test_terminate_active_processes_kills_ffmpeg_and_removes_output(tmp_path):
    """Verifies the exit hook kills running FFmpeg processes and deletes partial output."""
    output_file = tmp_path / "long_encode.mp4"
    cmd = _long_encode_command(output_file)

    worker = threading.Thread(
        target=video_ffmpeg_utils.run_strategies,
        args=([("long encode", cmd)], output_file, "long_encode.mp4"),
        daemon=True,
    )
    worker.start()

    # Wait until the process is registered in the active-process registry.
    deadline = time.perf_counter() + 5
    while not video_ffmpeg_utils._active_processes and time.perf_counter() < deadline:
        time.sleep(0.05)

    registered = list(video_ffmpeg_utils._active_processes)
    assert len(registered) == 1, (
        "[video] Running FFmpeg process was not registered in _active_processes within 5s."
    )

    video_ffmpeg_utils.terminate_active_processes()
    worker.join(timeout=10)

    assert not worker.is_alive(), (
        "[video] Worker thread blocked after terminate_active_processes() killed its FFmpeg child."
    )
    assert registered[0].poll() is not None, (
        "[video] Registered FFmpeg child process remained alive after terminate_active_processes()."
    )
    assert not output_file.exists(), (
        "[video] Partial output file was not cleaned up by terminate_active_processes()."
    )
    assert not video_ffmpeg_utils._active_processes, (
        "[video] _active_processes registry was not cleared after terminating active processes."
    )


def test_run_strategies_terminates_process_on_callback_exception(tmp_path, monkeypatch):
    """Verifies that an exception in progress_callback terminates FFmpeg and cleans output."""
    output_file = tmp_path / "long_encode.mp4"
    cmd = _long_encode_command(output_file)

    spawned: list[subprocess.Popen] = []
    original_popen = subprocess.Popen

    def recording_popen(*args, **kwargs):
        process = original_popen(*args, **kwargs)
        spawned.append(process)
        return process

    monkeypatch.setattr(video_ffmpeg_utils.subprocess, "Popen", recording_popen)

    def throwing_callback(out_time, fps, speed):
        raise InterruptedError("CANCELLED_IN_CALLBACK")

    with pytest.raises(InterruptedError):
        video_ffmpeg_utils.run_strategies(
            [("long encode", cmd)],
            output_file,
            "long_encode.mp4",
            progress_callback=throwing_callback,
        )

    assert len(spawned) == 1, (
        f"[video] Expected 1 FFmpeg process to spawn before callback exception, got {len(spawned)}."
    )
    assert spawned[0].poll() is not None, (
        "[video] FFmpeg process leaked as an orphan when progress_callback raised an exception."
    )
    assert not output_file.exists(), (
        "[video] Partial output file must be removed when progress_callback aborts execution."
    )
    assert len(video_ffmpeg_utils._active_processes) == 0, (
        "[video] Active process registry leaked entry after progress_callback raised an exception."
    )
