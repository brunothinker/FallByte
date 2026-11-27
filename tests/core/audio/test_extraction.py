"""Tests for single-file and batch directory audio extraction from video files."""

import subprocess
import threading
from pathlib import Path

import pytest

from src.audio import (
    audio_directory_extraction,
    audio_file_extraction,
)
from src.audio.utils import audio_ffmpeg_utils
from src.formats import AUDIO_TARGET_FORMATS
from src.utils import binary_manager
from tests.core.audio.helpers import (
    requires_libmp3lame,
    requires_libvorbis,
    skip_if_format_encoders_unavailable,
)


def _has_video_stream(ffmpeg_bin: Path, media_path: Path) -> bool:
    """Probes `media_path` via FFmpeg stderr to verify no video stream remains."""
    result = subprocess.run(
        [str(ffmpeg_bin), "-hide_banner", "-i", str(media_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return "Video:" in result.stderr


@pytest.mark.parametrize("target_fmt", AUDIO_TARGET_FORMATS)
def test_file_extractor_extracts_all_target_formats_and_strips_video(
    sample_video_factory, tmp_path: Path, target_fmt: str
):
    """Extracting audio from MP4 must succeed for all target formats and strip video streams."""
    skip_if_format_encoders_unavailable(target_fmt)
    src = sample_video_factory("clip.mp4", duration=1.0, with_audio=True)
    dst = tmp_path / "extracted" / f"clip.{target_fmt}"
    progress_calls: list[tuple[float, float, float, float]] = []

    res = audio_file_extraction.file_extractor(
        input_path=src,
        output_path=dst,
        target_format=target_fmt,
        file_progress_callback=lambda d, p, f, s: progress_calls.append((d, p, f, s)),
    )

    assert res.is_processed, (
        f"[audio] Extraction from MP4 to '{target_fmt}' unexpectedly failed or skipped: {res}."
    )
    assert dst.exists() and dst.stat().st_size > 0, (
        f"[audio] Extracted file '{dst}' was not created or is empty."
    )

    ffmpeg_bin = binary_manager.get_ffmpeg_path()
    probed = audio_ffmpeg_utils.probe_audio_streams(ffmpeg_bin, dst)
    assert probed.audio_codecs, (
        f"[audio] Probing extracted '{dst.name}' found no playable audio stream."
    )
    assert not _has_video_stream(ffmpeg_bin, dst), (
        f"[audio] Extracted '{dst.name}' still contains a video stream (`-vn` failed)."
    )
    assert progress_calls, (
        f"[audio] Expected progress callback to be invoked during extraction to '{target_fmt}'."
    )


@requires_libmp3lame
def test_file_extractor_skips_silent_video_without_audio_stream(
    sample_video_factory, tmp_path: Path
):
    """Videos lacking any audio stream must cleanly return skipped (`skip_no_audio_stream`) without creating output."""
    silent_video = sample_video_factory("silent.mp4", duration=0.8, with_audio=False)
    dst = tmp_path / "extracted" / "silent.mp3"

    res = audio_file_extraction.file_extractor(
        input_path=silent_video,
        output_path=dst,
        target_format="mp3",
    )

    assert res.is_skipped and res.reason_key == "skip_no_audio_stream", (
        f"[audio] Expected `file_extractor` to return skipped ('skip_no_audio_stream') for silent video, got {res}."
    )
    assert not res.is_failed and not res.is_processed, (
        f"[audio] Skipped silent video must not be marked failed or processed: {res}."
    )
    assert not dst.exists(), (
        "[audio] Silent video extraction must not leave an output file behind."
    )


def test_file_extractor_rejects_invalid_inputs_and_cleans_temp_on_cancel(
    sample_video_factory, tmp_path: Path
):
    """`file_extractor` must reject missing/empty/same-path files and clean temp files on cancellation."""
    res_missing = audio_file_extraction.file_extractor(
        tmp_path / "missing.mp4", tmp_path / "out.mp3", "mp3"
    )
    assert res_missing.is_failed and not res_missing, (
        "[audio] Missing video file must return failed FileResult without raising."
    )

    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    res_empty = audio_file_extraction.file_extractor(empty, tmp_path / "out.mp3", "mp3")
    assert res_empty.is_failed and not res_empty, (
        "[audio] Zero-byte video file must return failed FileResult."
    )

    valid = sample_video_factory("valid.mp4", duration=0.8)
    res_same = audio_file_extraction.file_extractor(valid, valid, "mp3")
    assert res_same.is_failed and not res_same, (
        "[audio] Extractor must refuse overwriting source file when input_path == output_path."
    )

    cancel = threading.Event()
    cancel.set()
    out_dir = tmp_path / "cancel_out"
    dst = out_dir / "valid.mp3"

    with pytest.raises(InterruptedError):
        audio_file_extraction.file_extractor(
            input_path=valid,
            output_path=dst,
            target_format="mp3",
            cancel_event=cancel,
        )

    assert not dst.exists(), (
        "[audio] Cancelled extraction must not leave behind a final output file."
    )
    leftover_tmps = list(out_dir.glob(".*_tmp_*")) if out_dir.exists() else []
    assert not leftover_tmps, (
        f"[audio] Cancelled extraction left temporary files behind: {leftover_tmps}."
    )


@requires_libvorbis
def test_file_extractor_triggers_rescue_stereo_fallback(
    sample_video_factory, tmp_path: Path, monkeypatch
):
    """When primary extraction strategy fails, `file_extractor` must recover via rescue stereo strategy."""
    ffmpeg_bin = binary_manager.get_ffmpeg_path()
    src = sample_video_factory("rescue_clip.mp4", duration=0.8)
    dst = tmp_path / "rescued.ogg"
    real_run = audio_ffmpeg_utils.run_audio_strategies

    def _fail_first_strategy(
        strategies, output_path, display_name, cancel_event=None, progress_callback=None
    ):
        assert len(strategies) >= 2, (
            f"[audio] Expected at least 2 strategies (primary + rescue), got {[s[0] for s in strategies]}."
        )
        broken_first = [
            ("forced_failure", [str(ffmpeg_bin), "-invalid_flag_to_force_fallback"])
        ]
        return real_run(
            broken_first + strategies[1:],
            output_path,
            display_name,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )

    monkeypatch.setattr(
        audio_file_extraction, "run_audio_strategies", _fail_first_strategy
    )

    res = audio_file_extraction.file_extractor(src, dst, target_format="ogg")
    assert res.is_processed, (
        f"[audio] file_extractor did not recover using the rescue stereo strategy: {res}."
    )
    assert dst.exists() and dst.stat().st_size > 0, (
        "[audio] Rescue audio extraction did not produce a non-empty output file."
    )


def test_scan_video_sources_recursive_and_non_recursive(tmp_path: Path):
    """`scan_video_sources` must discover supported video files case-insensitively and honor `recursive`."""
    (tmp_path / "clip_b.MP4").write_bytes(b"fake")
    (tmp_path / "clip_a.mkv").write_bytes(b"fake")
    (tmp_path / "song.mp3").write_bytes(b"ignore")
    (tmp_path / "readme.txt").write_text("ignore", encoding="utf-8")

    nested = tmp_path / "lectures"
    nested.mkdir()
    (nested / "lesson_01.MoV").write_bytes(b"fake")

    top_only = audio_directory_extraction.scan_video_sources(tmp_path, recursive=False)
    assert [p.name for p in top_only] == ["clip_a.mkv", "clip_b.MP4"], (
        f"[audio] Non-recursive video scan should return sorted top-level videos, got {[p.name for p in top_only]}."
    )

    all_files = audio_directory_extraction.scan_video_sources(tmp_path, recursive=True)
    assert [p.name for p in all_files] == [
        "clip_a.mkv",
        "clip_b.MP4",
        "lesson_01.MoV",
    ], (
        f"[audio] Recursive video scan should return all 3 sorted videos, got {[p.name for p in all_files]}."
    )

    assert audio_directory_extraction.scan_video_sources(tmp_path / "missing") == [], (
        "[audio] Scanning a non-existent directory must safely return an empty list."
    )


@requires_libmp3lame
def test_directory_extractor_preserves_hierarchy_handles_collisions_and_skips_silent(
    sample_video_factory, tmp_path: Path
):
    """`directory_extractor` must preserve folder hierarchy, skip silent videos, and avoid collisions."""
    in_dir = tmp_path / "videos"
    out_dir = tmp_path / "output"

    sample_video_factory("videos/talk.mp4", duration=0.8, with_audio=True)
    sample_video_factory("videos/talk.mkv", duration=0.8, with_audio=True)
    sample_video_factory("videos/module1/lesson.avi", duration=0.8, with_audio=True)
    sample_video_factory("videos/muted_broll.mp4", duration=0.6, with_audio=False)

    progress_events = []
    stats = audio_directory_extraction.directory_extractor(
        input_dir=in_dir,
        output_dir=out_dir,
        target_format="mp3",
        progress_callback=progress_events.append,
    )

    assert stats["total_files"] == 4, (
        f"[audio] Expected 4 scanned video files, got {stats['total_files']}."
    )
    assert stats["success"] == 3, (
        f"[audio] Expected 3 successful audio extractions, got {stats['success']} (stats={stats})."
    )
    assert stats["skipped"] == 1, (
        f"[audio] Expected 1 skipped extraction for silent video, got {stats['skipped']} (stats={stats})."
    )
    assert stats["failed"] == 0, (
        f"[audio] Expected 0 failed extractions for silent video, got {stats['failed']} (stats={stats})."
    )

    session_dir = out_dir / "extracted"
    extracted_mp3s = sorted(session_dir.rglob("*.mp3"))
    assert len(extracted_mp3s) == 3, (
        f"[audio] Expected 3 unique extracted MP3 files in '{session_dir}', got {extracted_mp3s}."
    )
    assert {p.name for p in extracted_mp3s} == {
        "talk.mp3",
        "talk_2.mp3",
        "lesson.mp3",
    }, (
        f"[audio] Batch extraction must keep original names, got {[p.name for p in extracted_mp3s]}."
    )
    assert (session_dir / "module1" / "lesson.mp3").exists(), (
        "[audio] Subdirectory structure 'module1/' was not preserved during batch extraction."
    )
    assert any(p.is_completed for p in progress_events), (
        "[audio] Expected `progress_callback` to emit completed ProgressInfo events."
    )


def test_directory_extractor_handles_empty_dir_and_cancellation(
    sample_video_factory, tmp_path: Path
):
    """Empty directories must return `no_files=True`, and cancellation must clean up session files."""
    empty_dir = tmp_path / "empty_videos"
    empty_dir.mkdir()
    out_dir = tmp_path / "out"

    empty_stats = audio_directory_extraction.directory_extractor(
        input_dir=empty_dir,
        output_dir=out_dir,
        target_format="wav",
    )
    assert empty_stats.get("no_files") is True and empty_stats["total_files"] == 0, (
        f"[audio] Expected `no_files=True` for empty directory, got {empty_stats}."
    )

    in_dir = tmp_path / "batch_cancel"
    sample_video_factory("batch_cancel/a.mp4", duration=0.6)
    sample_video_factory("batch_cancel/b.mp4", duration=0.6)

    cancel = threading.Event()

    def _cancel_after_first(info):
        if info.is_completed and info.current == 1:
            cancel.set()

    cancel_stats = audio_directory_extraction.directory_extractor(
        input_dir=in_dir,
        output_dir=out_dir,
        target_format="wav",
        progress_callback=_cancel_after_first,
        cancel_event=cancel,
    )

    assert cancel_stats["cancelled"] is True, (
        f"[audio] Expected `cancelled=True` when cancel_event triggered mid-batch, got {cancel_stats}."
    )
    assert cancel_stats["cleaned_files_count"] == 1, (
        f"[audio] Expected 1 previously created session file to be cleaned up, got {cancel_stats}."
    )
    assert not (out_dir / "extracted").exists(), (
        "[audio] Expected empty session directory 'extracted' to be removed after cancellation cleanup."
    )


@requires_libmp3lame
def test_file_extractor_preserves_source_audio_bitrate(
    sample_audio_factory, tmp_path: Path
):
    """`file_extractor` must reuse the probed source audio bitrate instead of inflating low-bitrate streams."""
    ffmpeg_bin = binary_manager.get_ffmpeg_path()
    low_mp3 = sample_audio_factory("low_64.mp3", duration=1.0, bitrate="64k")
    src = tmp_path / "low_audio.mp4"
    subprocess.run(
        [
            str(ffmpeg_bin),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=64x64:d=1.0:r=10",
            "-i",
            str(low_mp3),
            "-c:v",
            "mpeg4",
            "-c:a",
            "copy",
            "-shortest",
            str(src),
        ],
        check=True,
    )
    dst = tmp_path / "extracted_64.mp3"

    res = audio_file_extraction.file_extractor(
        input_path=src,
        output_path=dst,
        target_format="mp3",
    )
    assert res.is_processed
    probed = audio_ffmpeg_utils.probe_audio_streams(ffmpeg_bin, dst)
    assert probed.bitrate_kbps == 64, (
        f"[audio] Expected extracted MP3 from 64k audio track to stay at 64 kbps, got {probed.bitrate_kbps}."
    )
