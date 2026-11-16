"""Tests for single-file video conversion, progress callbacks, and I/O edge cases."""

import pytest

from src.image.image_file_conversion import file_converter
from src.video.video_file_conversion import file_converter as video_converter


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

    assert success is True, (
        f"[video] Video conversion from MP4 to '{target_format}' unexpectedly returned False."
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

    success = video_converter(
        src_mp4,
        dst_file,
        target_format="mkv",
        file_progress_callback=progress_cb,
    )

    assert success is True, (
        "[video] Video conversion with an active progress callback returned False."
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

    assert video_success is True, (
        "[video] Video conversion failed on paths containing Unicode accents, spaces, and symbols."
    )
    assert out_video.exists(), (
        "[video] Converted video was not created at Unicode destination path."
    )
    assert image_success is True, (
        "[video] Image conversion failed on paths containing Unicode accents, spaces, and symbols."
    )
    assert out_image.exists(), (
        "[video] Converted image was not created at Unicode destination path."
    )


def test_process_non_existent_file_handling(tmp_path):
    """Verifies that non-existent input paths return False or handle errors gracefully."""
    fake_input = tmp_path / "ghost_file.mp4"
    fake_output = tmp_path / "output.mp4"

    video_success = video_converter(
        fake_input, fake_output, target_format="mp4"
    )

    assert video_success is False, (
        "[video] Converting a non-existent input file must return False without raising."
    )
    assert not fake_output.exists(), (
        "[video] Failed conversion of a non-existent input must not create an output artifact."
    )


def test_process_corrupted_media_file_handling(tmp_path):
    """Verifies that corrupted media files are handled without crashing the runner."""
    corrupted_file = tmp_path / "corrupted_media.mp4"
    corrupted_file.write_bytes(b"NOT_A_VALID_MEDIA_HEADER")

    output_file = tmp_path / "failed_output.mp4"

    video_success = video_converter(
        corrupted_file, output_file, target_format="mp4"
    )

    assert video_success is False, (
        "[video] Converting a corrupted media file must return False gracefully."
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

    success = video_converter(corrupted_file, output_file, target_format="mp4")

    assert success is False, (
        "[video] Conversion of corrupted input must return False."
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

    success = video_converter(src_mp4, dst_mp4, target_format="mp4")

    assert success is False, (
        "[video] Simulated I/O error during same-format atomic copy must return False."
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