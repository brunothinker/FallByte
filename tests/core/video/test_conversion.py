"""Core (video): conversion tests."""

import subprocess
import threading
from pathlib import Path

import pytest

from src.image.image_file_conversion import file_converter
from src.utils.file_result import FileResult
from src.video import (
    video_directory_conversion as video_conversion,
)
from src.video import (
    video_file_conversion as conversion,
)
from src.video.utils.video_ffmpeg_utils import has_encoder, probe_streams
from src.video.video_file_conversion import file_converter as video_converter


def test_video_batch_conversion_cleans_up_when_cancelled(tmp_workspace, monkeypatch):
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
        return FileResult.processed()

    monkeypatch.setattr(video_conversion, "file_converter", fake_converter)

    stats = video_conversion.directory_converter(
        in_dir, out_dir, target_format="mp4", cancel_event=threading.Event()
    )

    assert stats["cancelled"] is True, (
        "[batch] InterruptedError during video batch conversion must set cancelled=True."
    )
    assert stats["cleaned_files_count"] == 1, (
        "[batch] Mid-batch cancellation must delete the 1 file created earlier in the same session."
    )
    assert not (out_dir / "converted").exists(), (
        "[batch] Empty 'converted' session directory must be removed after all session files are cleaned."
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
        return FileResult.processed()

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


@pytest.mark.parametrize("target_format", ["mkv", "avi", "mov", "webm", "mp4"])
def test_video_conversion_all_formats(
    tmp_workspace, create_sample_video, target_format
):
    """Tests video conversion across all supported container formats."""
    in_dir, out_dir = tmp_workspace
    src_mp4 = create_sample_video(in_dir / "input.mp4", duration_sec=1)

    dst_file = out_dir / f"output.{target_format}"
    res = video_converter(src_mp4, dst_file, target_format=target_format)

    if target_format == "mp4":
        assert (
            res
            and res.is_skipped
            and res.reason_key == "skip_same_format"
            and res.reason_params.get("fmt") == "mp4"
        ), (
            f"[video] Same-format MP4->MP4 conversion must return skipped ('skip_same_format'), got {res}."
        )
    else:
        assert res.is_processed, (
            f"[video] Video conversion from MP4 to '{target_format}' unexpectedly failed or skipped: {res}."
        )

    assert dst_file.exists(), (
        f"[video] Converted video file '{dst_file}' was not written to disk."
    )
    assert dst_file.stat().st_size > 0, (
        f"[video] Converted video file '{dst_file}' is empty (0 bytes)."
    )


def test_video_conversion_realtime_progress_callback(
    tmp_workspace, create_sample_video
):
    """Verifies that realtime progress callbacks receive duration, fps and speed during conversion."""
    in_dir, out_dir = tmp_workspace
    src_mp4 = create_sample_video(in_dir / "input.mp4", duration_sec=2)
    dst_file = out_dir / "output.mkv"

    progress_ticks = []

    def progress_cb(dur: float, proc: float, fps: float, speed: float) -> None:
        progress_ticks.append((dur, proc, fps, speed))

    res = video_converter(
        src_mp4,
        dst_file,
        target_format="mkv",
        file_progress_callback=progress_cb,
    )

    assert res.is_processed, (
        f"[video] Video conversion with an active progress callback failed: {res}."
    )
    assert len(progress_ticks) > 0, (
        "[video] Expected FFmpeg `-progress pipe:1` to emit at least one progress tick."
    )
    assert progress_ticks[-1][0] > 0.0, (
        "[video] Final progress tick must report a positive probed source duration."
    )


def test_process_files_with_special_characters_and_spaces(
    tmp_workspace, create_sample_video, create_sample_image
):
    """Ensures file processors handle paths with Unicode characters, spaces, and symbols."""
    in_dir, out_dir = tmp_workspace

    special_folder = in_dir / "Vídeos & Imagens de Teste (2026) #1"
    special_folder.mkdir(parents=True, exist_ok=True)

    special_video = special_folder / "test video 100%_ok.mp4"
    special_image = special_folder / "image with accents & spaces.png"

    create_sample_video(special_video, duration_sec=1)
    create_sample_image(special_image, mode="RGB", fmt="PNG")

    out_video = out_dir / "converted_video_output.mkv"
    out_image = out_dir / "converted_image_output.jpg"

    video_res = video_converter(special_video, out_video, target_format="mkv")
    image_res = file_converter(special_image, out_image, target_format="JPEG")

    assert video_res.is_processed, (
        f"[video] Video conversion failed on paths containing Unicode accents, spaces, and symbols: {video_res}."
    )
    assert out_video.exists(), (
        "[video] Converted video was not created at Unicode destination path."
    )
    assert image_res.is_processed, (
        f"[video] Image conversion failed on paths containing Unicode accents, spaces, and symbols: {image_res}."
    )
    assert out_image.exists(), (
        "[video] Converted image was not created at Unicode destination path."
    )


def test_process_non_existent_file_handling(tmp_path):
    """Verifies that non-existent input paths return failed FileResult or handle errors gracefully."""
    fake_input = tmp_path / "ghost_file.mp4"
    fake_output = tmp_path / "output.mp4"

    video_res = video_converter(fake_input, fake_output, target_format="mp4")

    assert video_res.is_failed and not video_res, (
        f"[video] Converting a non-existent input file must return failed FileResult without raising, got {video_res}."
    )
    assert not fake_output.exists(), (
        "[video] Failed conversion of a non-existent input must not create an output artifact."
    )


def test_process_corrupted_media_file_handling(tmp_path):
    """Verifies that corrupted media files are handled without crashing the runner."""
    corrupted_file = tmp_path / "corrupted_media.mp4"
    corrupted_file.write_bytes(b"NOT_A_VALID_MEDIA_HEADER")

    output_file = tmp_path / "failed_output.mp4"

    video_res = video_converter(corrupted_file, output_file, target_format="mp4")

    assert video_res.is_failed and not video_res, (
        f"[video] Converting a corrupted media file must return failed FileResult gracefully, got {video_res}."
    )
    assert not output_file.exists(), (
        "[video] Corrupted input conversion must not leave behind a partial output file."
    )


def test_video_conversion_atomic_write_on_failure(tmp_workspace):
    """Ensures video conversion failure preserves pre-existing target file."""
    in_dir, out_dir = tmp_workspace
    corrupted_file = in_dir / "corrupted_media.mp4"
    corrupted_file.write_bytes(b"NOT_A_VALID_MEDIA_HEADER")

    output_file = out_dir / "existing_output.mp4"
    output_file.write_bytes(b"original data")

    res = video_converter(corrupted_file, output_file, target_format="mp4")

    assert res.is_failed and not res, (
        f"[video] Conversion of corrupted input must return failed FileResult, got {res}."
    )
    assert output_file.exists(), (
        "[video] Failed video conversion must not delete a pre-existing destination file."
    )
    assert output_file.read_bytes() == b"original data", (
        "[video] Failed video conversion must leave pre-existing destination bytes untouched."
    )
    assert list(out_dir.glob(".*_tmp_*")) == [], (
        "[video] Failed video conversion leaked temporary files in the output directory."
    )


def test_video_conversion_same_format_atomic_copy_on_failure(
    tmp_workspace, create_sample_video, monkeypatch
):
    """Ensures failure during same-format bypass copy preserves existing output and cleans tmp files."""
    in_dir, out_dir = tmp_workspace
    src_mp4 = create_sample_video(in_dir / "input.mp4", duration_sec=1)
    dst_mp4 = out_dir / "output.mp4"
    dst_mp4.write_bytes(b"original destination data")

    def failing_copy2(*args, **kwargs):
        raise OSError("Simulated disk error during same-format copy")

    monkeypatch.setattr("src.utils.cleanup.shutil.copy2", failing_copy2)

    res = video_converter(src_mp4, dst_mp4, target_format="mp4")

    assert res.is_failed and not res, (
        f"[video] Simulated I/O error during same-format atomic copy must return failed FileResult, got {res}."
    )
    assert dst_mp4.exists(), (
        "[video] Failed same-format bypass copy must not delete pre-existing destination file."
    )
    assert dst_mp4.read_bytes() == b"original destination data", (
        "[video] Failed same-format bypass copy must preserve pre-existing destination bytes."
    )
    assert list(out_dir.glob(".*_tmp_*")) == [], (
        "[video] Failed same-format bypass copy leaked temporary files in the output directory."
    )


@pytest.mark.parametrize("container", ["mp4", "mov", "mkv"])
@pytest.mark.parametrize("x265_available", [True, False])
def test_hevc_reencode_strategies(container, x265_available, monkeypatch):
    monkeypatch.setattr(conversion, "has_encoder", lambda *_: x265_available)
    strategies = dict(
        conversion._build_strategies(
            Path("ffmpeg"),
            Path("input.ts"),
            Path(f"out.{container}"),
            container,
            "hevc",
            False,
            True,
            is_10bit=True,
        )
    )
    for name in ("safe re-encode", "rescue re-encode"):
        command = strategies[name]
        assert command[command.index("-c:v") + 1] == (
            "libx265" if x265_available else "libx264"
        )
        assert command[command.index("-pix_fmt") + 1] == (
            "yuv420p10le" if x265_available else "yuv420p"
        )
        if x265_available and container in ("mp4", "mov"):
            assert command[command.index("-tag:v") + 1] == "hvc1"
        else:
            assert "-tag:v" not in command
    if x265_available:
        command = strategies["h264 fallback"]
        assert command[command.index("-c:v") + 1] == "libx264"
        assert command[command.index("-pix_fmt") + 1] == "yuv420p"
        assert "-tag:v" not in command


@pytest.mark.parametrize("container", ["mp4", "mov", "mkv"])
def test_convert_10bit_hevc(tmp_path, container):
    try:
        ffmpeg = conversion.get_ffmpeg_path()
    except (FileNotFoundError, OSError) as err:
        pytest.skip(str(err))
    if not has_encoder(ffmpeg, "libx265"):
        pytest.skip("FFmpeg has no libx265 encoder")
    source = tmp_path / ("source.mp4" if container == "mkv" else "source.mkv")
    subprocess.run(
        [
            str(ffmpeg),
            "-nostdin",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=64x64:rate=5,format=yuv420p10le",
            "-frames:v",
            "2",
            "-c:v",
            "libx265",
            "-pix_fmt",
            "yuv420p10le",
            str(source),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    target = tmp_path / f"output.{container}"
    res = conversion.file_converter(source, target, container)
    assert res.is_processed
    output = probe_streams(ffmpeg, target)
    assert (output.video_codec, output.pix_fmt) == ("hevc", "yuv420p10le")
