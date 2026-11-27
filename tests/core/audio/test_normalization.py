"""Tests for single-file and batch directory EBU R128 audio loudness normalization."""

import threading
from pathlib import Path

import pytest

from src.audio import (
    audio_directory_normalization,
    audio_file_normalization,
)
from src.audio.utils import audio_ffmpeg_utils
from src.formats import NORMALIZABLE_AUDIO_FORMATS
from src.utils import binary_manager
from tests.core.audio.helpers import (
    requires_libmp3lame,
    requires_libvorbis,
    skip_if_format_encoders_unavailable,
)


def test_resolve_loudness_preset_and_filter_string():
    """`resolve_loudness_preset` must return exact EBU R128 targets and reject unknown presets."""
    music = audio_file_normalization.resolve_loudness_preset("music")
    assert (
        music.integrated_lufs == -14.0
        and music.true_peak_dbtp == -1.0
        and music.lra == 11.0
    ), f"[audio] Unexpected 'music' loudness preset parameters: {music}."
    assert music.to_filter_arg() == "loudnorm=I=-14.0:TP=-1.0:LRA=11.0", (
        f"[audio] Unexpected loudnorm filter string for 'music': {music.to_filter_arg()!r}."
    )

    podcast = audio_file_normalization.resolve_loudness_preset("  PODCAST ")
    assert (
        podcast.integrated_lufs == -16.0
        and podcast.true_peak_dbtp == -1.5
        and podcast.lra == 7.0
    ), f"[audio] Unexpected 'podcast' loudness preset parameters: {podcast}."
    assert podcast.to_filter_arg() == "loudnorm=I=-16.0:TP=-1.5:LRA=7.0", (
        f"[audio] Unexpected loudnorm filter string for 'podcast': {podcast.to_filter_arg()!r}."
    )

    broadcast = audio_file_normalization.resolve_loudness_preset("broadcast")
    assert (
        broadcast.integrated_lufs == -23.0
        and broadcast.true_peak_dbtp == -2.0
        and broadcast.lra == 7.0
    ), f"[audio] Unexpected 'broadcast' loudness preset parameters: {broadcast}."
    assert broadcast.to_filter_arg() == "loudnorm=I=-23.0:TP=-2.0:LRA=7.0", (
        f"[audio] Unexpected loudnorm filter string for 'broadcast': {broadcast.to_filter_arg()!r}."
    )

    with pytest.raises(ValueError, match="Unsupported loudness preset"):
        audio_file_normalization.resolve_loudness_preset("club_bass_boost")


@pytest.mark.parametrize(
    "ext", sorted(NORMALIZABLE_AUDIO_FORMATS)
)
def test_file_normalizer_normalizes_all_supported_formats_and_preserves_format(
    sample_audio_factory, tmp_path: Path, ext: str
):
    """`file_normalizer` must normalize audio across all supported formats while preserving format and sample rate."""
    skip_if_format_encoders_unavailable(ext)
    src = sample_audio_factory(f"track.{ext}", duration=1.2)
    dst = tmp_path / "normalized" / f"track.{ext}"
    progress_calls: list[tuple[float, float, float, float]] = []

    res = audio_file_normalization.file_normalizer(
        input_path=src,
        output_path=dst,
        preset_key="music",
        file_progress_callback=lambda d, p, f, s: progress_calls.append((d, p, f, s)),
    )

    assert res.is_processed, (
        f"[audio] Normalization of '{src.name}' unexpectedly failed or skipped: {res}."
    )
    assert dst.exists() and dst.stat().st_size > 0, (
        f"[audio] Normalized output '{dst}' was not created or is empty."
    )

    ffmpeg_bin = binary_manager.get_ffmpeg_path()
    probed = audio_ffmpeg_utils.probe_audio_streams(ffmpeg_bin, dst)
    assert probed.audio_codecs, (
        f"[audio] Probing normalized '{dst.name}' found no playable audio stream."
    )
    if ext == "opus":
        assert probed.sample_rate == 48000, (
            f"[audio] Expected Opus output sample rate 48000 Hz, got {probed.sample_rate}."
        )
    else:
        assert probed.sample_rate == 44100, (
            f"[audio] Expected normalized '{ext}' to preserve 44100 Hz sample rate (not loudnorm's 192 kHz), "
            f"got {probed.sample_rate}."
        )
    assert progress_calls, (
        f"[audio] Expected `file_progress_callback` to be invoked during '{ext}' normalization."
    )


@requires_libmp3lame
@pytest.mark.parametrize("preset_key", ["music", "podcast", "broadcast"])
def test_file_normalizer_succeeds_for_all_presets(
    sample_audio_factory, tmp_path: Path, preset_key: str
):
    """`file_normalizer` must succeed cleanly for every registered loudness preset."""
    src = sample_audio_factory(f"voice_{preset_key}.mp3", duration=1.2, bitrate="192k")
    dst = tmp_path / "out" / f"voice_{preset_key}.mp3"

    res = audio_file_normalization.file_normalizer(
        input_path=src,
        output_path=dst,
        preset_key=preset_key,
    )

    assert res.is_processed, (
        f"[audio] Normalization with preset '{preset_key}' unexpectedly failed or skipped: {res}."
    )
    assert dst.exists() and dst.stat().st_size > 0, (
        f"[audio] Output file for preset '{preset_key}' is missing or empty."
    )


def test_file_normalizer_rejects_invalid_inputs_skips_unsupported_and_cleans_temp_on_cancel(
    sample_audio_factory, tmp_path: Path
):
    """`file_normalizer` must fail on missing/empty/same-path/corrupt, skip unsupported formats, and clean temp on cancel."""
    res_missing = audio_file_normalization.file_normalizer(
        tmp_path / "missing.mp3", tmp_path / "out.mp3"
    )
    assert res_missing.is_failed and not res_missing, (
        "[audio] Missing source file must return failed FileResult without raising."
    )

    empty = tmp_path / "empty.mp3"
    empty.write_bytes(b"")
    res_empty = audio_file_normalization.file_normalizer(empty, tmp_path / "out.mp3")
    assert res_empty.is_failed and not res_empty, (
        "[audio] Zero-byte source file must return failed FileResult."
    )

    valid = sample_audio_factory("valid.wav", duration=0.8)
    res_same = audio_file_normalization.file_normalizer(valid, valid)
    assert res_same.is_failed and not res_same, (
        "[audio] Normalizer must refuse overwriting source file when input_path == output_path."
    )

    aiff_file = sample_audio_factory("unsupported.aiff", duration=0.6)
    aiff_out = tmp_path / "out.aiff"
    res_aiff = audio_file_normalization.file_normalizer(aiff_file, aiff_out)
    assert (
        res_aiff.is_skipped
        and res_aiff.reason_key == "skip_unsupported_normalization_format"
        and res_aiff.reason_params.get("fmt") == "aiff"
    ), (
        f"[audio] Unsupported container format '.aiff' must return skipped ('skip_unsupported_normalization_format'), got {res_aiff}."
    )
    assert not aiff_out.exists(), (
        "[audio] Unsupported format normalization must not create an output file."
    )

    corrupt = tmp_path / "corrupt.mp3"
    corrupt.write_bytes(b"not-a-valid-audio-stream")
    res_corrupt = audio_file_normalization.file_normalizer(
        corrupt, tmp_path / "out.mp3"
    )
    assert res_corrupt.is_failed and not res_corrupt, (
        "[audio] Corrupted audio file without streams must return failed FileResult."
    )

    cancel = threading.Event()
    cancel.set()
    out_dir = tmp_path / "cancel_out"
    dst = out_dir / "valid.wav"

    with pytest.raises(InterruptedError):
        audio_file_normalization.file_normalizer(
            input_path=valid,
            output_path=dst,
            cancel_event=cancel,
        )

    assert not dst.exists(), (
        "[audio] Cancelled normalization must not leave a final output file behind."
    )
    leftover_tmps = list(out_dir.glob(".*_tmp_*")) if out_dir.exists() else []
    assert not leftover_tmps, (
        f"[audio] Cancelled normalization left temporary files behind: {leftover_tmps}."
    )


@requires_libvorbis
def test_file_normalizer_triggers_rescue_stereo_fallback(
    sample_audio_factory, tmp_path: Path, monkeypatch
):
    """When primary `loudnorm` strategy fails, `file_normalizer` must recover via rescue stereo strategy."""
    ffmpeg_bin = binary_manager.get_ffmpeg_path()
    src = sample_audio_factory("rescue_norm.ogg", duration=0.8)
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
        audio_file_normalization, "run_audio_strategies", _fail_first_strategy
    )

    res = audio_file_normalization.file_normalizer(src, dst, preset_key="podcast")
    assert res.is_processed, (
        f"[audio] file_normalizer did not recover using the rescue stereo strategy: {res}."
    )
    assert dst.exists() and dst.stat().st_size > 0, (
        "[audio] Rescue loudness normalization did not produce a non-empty output file."
    )


def test_scan_normalizable_audio_files_filters_unsupported_formats(tmp_path: Path):
    """`scan_normalizable_audio_files` must include normalizable audio formats and skip `.wma`/`.aiff`."""
    (tmp_path / "song.mp3").write_bytes(b"fake")
    (tmp_path / "master.flac").write_bytes(b"fake")
    (tmp_path / "legacy.wma").write_bytes(b"skip")
    (tmp_path / "studio.aiff").write_bytes(b"skip")
    (tmp_path / "video.mp4").write_bytes(b"skip")

    nested = tmp_path / "album"
    nested.mkdir()
    (nested / "intro.ogg").write_bytes(b"fake")

    found = audio_directory_normalization.scan_normalizable_audio_files(
        tmp_path, recursive=True
    )
    assert [p.name for p in found] == ["intro.ogg", "master.flac", "song.mp3"], (
        f"[audio] Expected only normalizable formats in sorted order, got {[p.name for p in found]}."
    )


@requires_libmp3lame
def test_directory_normalizer_preserves_hierarchy_and_isolates_failures(
    sample_audio_factory, tmp_path: Path
):
    """`directory_normalizer` must preserve folder hierarchy, isolate broken files, and leave sources untouched."""
    in_dir = tmp_path / "music_pack"
    out_dir = tmp_path / "output"

    src_root = sample_audio_factory("music_pack/track01.mp3", duration=1.0, bitrate="192k")
    orig_bytes = src_root.read_bytes()
    sample_audio_factory("music_pack/disc2/track02.wav", duration=1.0)
    (in_dir / "broken.mp3").write_bytes(b"corrupted-audio")

    progress_events = []
    stats = audio_directory_normalization.directory_normalizer(
        input_dir=in_dir,
        output_dir=out_dir,
        preset_key="music",
        progress_callback=progress_events.append,
    )

    assert stats["total_files"] == 3, (
        f"[audio] Expected 3 scanned normalizable files, got {stats['total_files']}."
    )
    assert stats["success"] == 2, (
        f"[audio] Expected 2 successful normalizations, got {stats['success']} (stats={stats})."
    )
    assert stats["skipped"] == 0, (
        f"[audio] Expected 0 skipped normalizations, got {stats['skipped']} (stats={stats})."
    )
    assert stats["failed"] == 1, (
        f"[audio] Expected 1 failed normalization for corrupted file, got {stats['failed']}."
    )

    session_dir = out_dir / "normalized"
    dst_root = session_dir / "track01.mp3"
    dst_nested = session_dir / "disc2" / "track02.wav"

    assert dst_root.exists() and dst_root.stat().st_size > 0, (
        "[audio] Normalized top-level MP3 file is missing or empty."
    )
    assert dst_nested.exists() and dst_nested.stat().st_size > 0, (
        "[audio] Subdirectory structure 'disc2/' was not preserved during batch normalization."
    )
    assert src_root.read_bytes() == orig_bytes, (
        "[audio] Source audio file was modified during normalization."
    )
    assert any(p.is_completed for p in progress_events), (
        "[audio] Expected `progress_callback` to emit completed ProgressInfo events."
    )


def test_directory_normalizer_handles_empty_dir_and_cancellation(
    sample_audio_factory, tmp_path: Path
):
    """Empty directories must return `no_files=True`, and cancellation must clean up session files."""
    empty_dir = tmp_path / "empty_audio"
    empty_dir.mkdir()
    out_dir = tmp_path / "out"

    empty_stats = audio_directory_normalization.directory_normalizer(
        input_dir=empty_dir,
        output_dir=out_dir,
        preset_key="broadcast",
    )
    assert empty_stats.get("no_files") is True and empty_stats["total_files"] == 0, (
        f"[audio] Expected `no_files=True` for empty directory, got {empty_stats}."
    )

    in_dir = tmp_path / "batch_cancel"
    sample_audio_factory("batch_cancel/a.wav", duration=0.8)
    sample_audio_factory("batch_cancel/b.wav", duration=0.8)

    cancel = threading.Event()

    def _cancel_after_first(info):
        if info.is_completed and info.current == 1:
            cancel.set()

    cancel_stats = audio_directory_normalization.directory_normalizer(
        input_dir=in_dir,
        output_dir=out_dir,
        preset_key="podcast",
        progress_callback=_cancel_after_first,
        cancel_event=cancel,
    )

    assert cancel_stats["cancelled"] is True, (
        f"[audio] Expected `cancelled=True` when cancel_event triggered mid-batch, got {cancel_stats}."
    )
    assert cancel_stats["cleaned_files_count"] == 1, (
        f"[audio] Expected 1 previously created session file to be cleaned up, got {cancel_stats}."
    )
    assert not (out_dir / "normalized").exists(), (
        "[audio] Expected empty session directory 'normalized' to be removed after cancellation cleanup."
    )


@requires_libmp3lame
def test_file_normalizer_preserves_high_and_low_source_bitrates(
    sample_audio_factory, tmp_path: Path
):
    """`file_normalizer` must preserve 320 kbps sources and avoid inflating 64 kbps sources."""
    ffmpeg_bin = binary_manager.get_ffmpeg_path()

    src_320 = sample_audio_factory("hi.mp3", duration=1.0, bitrate="320k")
    dst_320 = tmp_path / "out_320.mp3"
    res_320 = audio_file_normalization.file_normalizer(src_320, dst_320)
    assert res_320.is_processed
    probed_320 = audio_ffmpeg_utils.probe_audio_streams(ffmpeg_bin, dst_320)
    assert probed_320.bitrate_kbps == 320, (
        f"[audio] Expected 320 kbps MP3 to keep 320 kbps after normalization, got {probed_320.bitrate_kbps}."
    )

    src_64 = sample_audio_factory("speech.mp3", duration=1.0, bitrate="64k")
    dst_64 = tmp_path / "out_64.mp3"
    res_64 = audio_file_normalization.file_normalizer(src_64, dst_64)
    assert res_64.is_processed
    probed_64 = audio_ffmpeg_utils.probe_audio_streams(ffmpeg_bin, dst_64)
    assert probed_64.bitrate_kbps == 64, (
        f"[audio] Expected 64 kbps MP3 not to be inflated to 192 kbps, got {probed_64.bitrate_kbps}."
    )


def test_parse_loudnorm_json_extracts_finite_metrics_and_rejects_silence() -> None:
    """`parse_loudnorm_json` must parse valid FFmpeg JSON blocks and return None for `-inf`/invalid output."""
    sample_stderr = """
    [Parsed_loudnorm_0 @ 0x55a1]
    {
        "input_i" : "-18.42",
        "input_tp" : "-2.15",
        "input_lra" : "6.80",
        "input_thresh" : "-28.90",
        "output_i" : "-14.01",
        "output_tp" : "-1.00",
        "output_lra" : "6.50",
        "output_thresh" : "-24.50",
        "normalization_type" : "linear",
        "target_offset" : "4.42"
    }
    """
    parsed = audio_file_normalization.parse_loudnorm_json(sample_stderr)
    assert parsed is not None
    assert parsed.input_i == pytest.approx(-18.42)
    assert parsed.input_tp == pytest.approx(-2.15)
    assert parsed.input_lra == pytest.approx(6.80)
    assert parsed.input_thresh == pytest.approx(-28.90)
    assert parsed.target_offset == pytest.approx(4.42)

    preset = audio_file_normalization.resolve_loudness_preset("music")
    linear_arg = parsed.to_linear_filter_arg(preset)
    assert "measured_I=-18.42" in linear_arg
    assert "measured_TP=-2.15" in linear_arg
    assert "measured_LRA=6.80" in linear_arg
    assert "measured_thresh=-28.90" in linear_arg
    assert "offset=4.42" in linear_arg
    assert "linear=true" in linear_arg

    silent_stderr = """
    {
        "input_i" : "-inf",
        "input_tp" : "-inf",
        "input_lra" : "0.00",
        "input_thresh" : "-inf",
        "target_offset" : "inf"
    }
    """
    assert audio_file_normalization.parse_loudnorm_json(silent_stderr) is None
    assert audio_file_normalization.parse_loudnorm_json("no json output") is None


def test_file_normalizer_two_pass_injects_measured_linear_params_and_splits_progress(
    sample_audio_factory, tmp_path: Path, monkeypatch
) -> None:
    """Mocked Pass-1 measurement must feed Pass 2 with `measured_*` + `linear=true` and split progress 0-50% / 50-100%."""
    src = sample_audio_factory("two_pass_mock.wav", duration=2.0)
    dst = tmp_path / "out_linear.wav"

    mock_measurement = audio_file_normalization.LoudnormMeasurement(
        input_i=-20.5,
        input_tp=-3.1,
        input_lra=5.4,
        input_thresh=-31.2,
        target_offset=6.5,
    )

    def _fake_pass1(ffmpeg_bin, input_path, preset, cancel_event=None, progress_callback=None):
        if progress_callback:
            progress_callback(1.0, 0.0, 4.0)
            progress_callback(2.0, 0.0, 4.0)
        return audio_file_normalization.Pass1Result(measurement=mock_measurement)

    captured_cmds: list[list[str]] = []
    real_run = audio_ffmpeg_utils.run_audio_strategies

    def _capture_pass2(
        strategies, output_path, display_name, cancel_event=None, progress_callback=None
    ):
        captured_cmds.append(strategies[0][1])
        return real_run(
            strategies,
            output_path,
            display_name,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )

    monkeypatch.setattr(audio_file_normalization, "_measure_loudnorm_pass", _fake_pass1)
    monkeypatch.setattr(audio_file_normalization, "run_audio_strategies", _capture_pass2)

    progress_events: list[tuple[float, float]] = []
    res = audio_file_normalization.file_normalizer(
        input_path=src,
        output_path=dst,
        preset_key="music",
        file_progress_callback=lambda dur, proc, _fps, _spd: progress_events.append((dur, proc)),
    )

    assert res.is_processed
    assert dst.exists() and dst.stat().st_size > 0
    assert len(captured_cmds) == 1

    af_idx = captured_cmds[0].index("-af")
    filter_val = captured_cmds[0][af_idx + 1]
    assert "measured_I=-20.50" in filter_val
    assert "measured_TP=-3.10" in filter_val
    assert "measured_LRA=5.40" in filter_val
    assert "measured_thresh=-31.20" in filter_val
    assert "offset=6.50" in filter_val
    assert "linear=true" in filter_val

    # Pass 1 reports up to 50% (1.0s of 2.0s), Pass 2 advances from 50% to 100% (2.0s of 2.0s)
    processed_values = [proc for _dur, proc in progress_events]
    assert any(0.0 < p <= 1.0 for p in processed_values), f"Missing Pass-1 half progress: {processed_values}"
    assert any(p > 1.0 for p in processed_values), f"Missing Pass-2 second-half progress: {processed_values}"


@pytest.mark.parametrize("ext", ["wav", "flac", "mp3", "m4a"])
def test_file_normalizer_handles_silent_audio_fallback_across_formats(
    tmp_path: Path, ext: str
) -> None:
    """Completely silent audio (`input_i=-inf`) must fall back to single-pass and succeed across formats."""
    import subprocess

    skip_if_format_encoders_unavailable(ext)
    ffmpeg_bin = binary_manager.get_ffmpeg_path()
    src = tmp_path / f"silence.{ext}"
    dst = tmp_path / "out" / f"silence_norm.{ext}"

    codec_args = audio_ffmpeg_utils.get_audio_codec_args(ext, quality=None)
    subprocess.run(
        [
            str(ffmpeg_bin),
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=stereo",
            "-t",
            "0.8",
            *codec_args,
            str(src),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    res = audio_file_normalization.file_normalizer(src, dst, preset_key="podcast")
    assert res.is_skipped and res.reason_key == "skip_silent_audio", (
        f"[audio] Silent '{ext}' must copy original as skipped ('skip_silent_audio'), got {res}."
    )
    assert dst.exists() and dst.stat().st_size > 0
