"""HEVC compression and 10-bit color preservation tests.

Pins three things:
  * HEVC sources (mp4/mov/mkv) are compressed with libx265 and keep the hvc1 tag;
  * 10-bit HEVC sources preserve yuv420p10le pixel format when encoding with libx265;
  * every other source keeps the original libx264/VP9/WMV2 behavior (regression);
  * if libx265 is missing or fails, compression falls back to the old H.264 path.

Integration tests need the bundled FFmpeg with libx265 and are skipped otherwise.
"""

import subprocess
from pathlib import Path

import pytest

from src.utils.binary_manager import get_ffmpeg_path
from src.video import video_file_compression as vc
from src.video.utils import video_ffmpeg_utils
from src.video.utils.video_ffmpeg_utils import (
    get_codec_args,
    get_video_filter,
    probe_streams,
)

FFMPEG = Path("ffmpeg")


def _codec_of(args: list[str]) -> str:
    return args[args.index("-c:v") + 1]


def _crf_of(args: list[str]) -> int:
    return int(args[args.index("-crf") + 1])


def _strategies(ext, quality=80, codec=None, hevc_available=False, is_10bit=False):
    return vc._build_strategies(
        FFMPEG,
        Path("in.mp4"),
        Path("out.tmp"),
        ext,
        quality,
        codec,
        hevc_available,
        is_10bit,
    )


def _video_line(path: Path) -> str:
    """Returns the `Video:` line printed by `ffmpeg -i` (shows codec and tag)."""
    try:
        ffmpeg_bin = get_ffmpeg_path()
    except (FileNotFoundError, OSError):
        return ""

    result = subprocess.run(
        [str(ffmpeg_bin), "-hide_banner", "-i", str(path)],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    for line in result.stderr.decode("utf-8", errors="ignore").splitlines():
        if "Video:" in line:
            return line
    return ""


def _x265_available() -> bool:
    """Checks whether the bundled FFmpeg binary exists and supports libx265 encoding."""
    try:
        ffmpeg_bin = get_ffmpeg_path()
        return video_ffmpeg_utils.has_encoder(ffmpeg_bin, "libx265")
    except (FileNotFoundError, OSError):
        return False


needs_x265 = pytest.mark.skipif(
    not _x265_available(),
    reason="bundled FFmpeg has no libx265",
)


# --- get_video_filter & 10-bit preservation: unit ---


def test_get_video_filter_preserves_10bit_for_hevc():
    """10-bit pixel format must be yuv420p10le only when encoding to HEVC."""
    assert get_video_filter(is_10bit=True, keep_hevc=True) == [
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-pix_fmt",
        "yuv420p10le",
    ], (
        "[video] 10-bit source with keep_hevc=True must preserve yuv420p10le pixel format."
    )
    assert get_video_filter(is_10bit=True, keep_hevc=False) == [
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-pix_fmt",
        "yuv420p",
    ], (
        "[video] 10-bit source falling back to H.264 (keep_hevc=False) must downsample to 8-bit yuv420p."
    )
    assert get_video_filter(is_10bit=False, keep_hevc=True) == [
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-pix_fmt",
        "yuv420p",
    ], (
        "[video] 8-bit HEVC source must retain standard yuv420p rather than upconverting to 10-bit."
    )


# --- get_codec_args: unit ---


def test_conversion_defaults_are_unchanged():
    """Conversion calls (no quality) must never be affected by the HEVC path."""
    assert get_codec_args("mp4") == ["-c:v", "libx264", "-c:a", "aac"], (
        "[video] Default MP4 conversion args regressed from libx264 + aac."
    )
    assert get_codec_args("mp4", None, "hevc") == ["-c:v", "libx264", "-c:a", "aac"], (
        "[video] Conversion mode (quality=None) must still target libx264 even when source is HEVC."
    )


@pytest.mark.parametrize("ext", ["mp4", "mov", "mkv", "avi"])
@pytest.mark.parametrize("quality", [1, 30, 60, 80, 100])
def test_h264_compression_args_are_unchanged(ext, quality):
    """Regression: without a HEVC source the CRF mapping is the original one."""
    expected_crf = round(18 + (100 - quality) * 0.22)
    for codec in (None, "h264", "vp9", "av1"):
        args = get_codec_args(ext, quality, codec)
        assert _codec_of(args) == "libx264", (
            f"[video] Non-HEVC source '{codec}' in '{ext}' must keep libx264 encoder."
        )
        assert _crf_of(args) == expected_crf, (
            f"[video] H.264 CRF formula regressed at quality={quality}: expected {expected_crf}, got {_crf_of(args)}."
        )


@pytest.mark.parametrize("ext", ["mp4", "mov", "mkv"])
def test_hevc_compression_uses_libx265(ext):
    """Verifies HEVC sources in MP4/MOV/MKV select libx265 with the +5 CRF perceptual offset."""
    args = get_codec_args(ext, 80, "hevc")
    assert _codec_of(args) == "libx265", (
        f"[video] HEVC source in '{ext}' should compress with libx265 to preserve efficiency."
    )
    assert _crf_of(args) == round(23 + (100 - 80) * 0.22), (
        f"[video] HEVC CRF mapping regressed for '{ext}' at quality=80."
    )


@pytest.mark.parametrize(
    "ext,expected",
    [("avi", "libx264"), ("webm", "libvpx-vp9"), ("wmv", "wmv2")],
)
def test_hevc_in_other_containers_keeps_container_codec(ext, expected):
    """Verifies containers without standard HEVC support retain their native target codec."""
    assert _codec_of(get_codec_args(ext, 80, "hevc")) == expected, (
        f"[video] Container '{ext}' must use '{expected}' rather than forcing libx265."
    )


def test_hevc_quality_slider_is_monotonic_and_within_range():
    """Lower quality -> higher CRF, same slope as x264, always valid for x265 (0-51)."""
    crfs = [_crf_of(get_codec_args("mp4", q, "hevc")) for q in range(1, 101)]
    assert crfs == sorted(crfs, reverse=True), (
        "[video] HEVC CRF curve must decrease monotonically as quality increases from 1 to 100."
    )
    assert all(0 <= c <= 51 for c in crfs), (
        "[video] Computed HEVC CRF values must stay within valid libx265 range (0..51)."
    )
    h264 = [_crf_of(get_codec_args("mp4", q)) for q in range(1, 101)]
    assert {x - h for x, h in zip(crfs, h264)} <= {4, 5, 6}, (
        "[video] HEVC CRF curve must maintain a ~5-point perceptual offset above H.264 CRF."
    )


# --- _build_strategies: unit ---


@pytest.mark.parametrize("ext", ["mp4", "mov"])
def test_hevc_strategies_tag_hvc1_and_fall_back_to_h264(ext):
    """Verifies MP4/MOV HEVC strategies emit `-tag:v hvc1` and append an H.264 rescue fallback."""
    strategies = dict(_strategies(ext, codec="hevc", hevc_available=True))

    for label in ("safe re-encode", "rescue re-encode"):
        cmd = strategies[label]
        assert _codec_of(cmd) == "libx265", (
            f"[video] Primary HEVC strategy '{label}' for '{ext}' must use libx265."
        )
        assert cmd[cmd.index("-tag:v") + 1] == "hvc1", (
            f"[video] Strategy '{label}' for '{ext}' must tag HEVC streams with 'hvc1' for Apple/player compatibility."
        )

    fallback = strategies["h264 fallback"]
    assert _codec_of(fallback) == "libx264", (
        "[video] Final fallback strategy for HEVC sources must transcode with libx264."
    )
    assert "-tag:v" not in fallback, (
        "[video] H.264 fallback command must not carry the HEVC-only '-tag:v hvc1' flag."
    )
    assert list(strategies)[-1] == "h264 fallback", (
        "[video] 'h264 fallback' must be ordered last so libx265 strategies are tried first."
    )


def test_hevc_10bit_strategies_use_yuv420p10le():
    """Validates that HEVC 10-bit strategies include yuv420p10le pixel format."""
    strategies = dict(
        _strategies("mp4", codec="hevc", hevc_available=True, is_10bit=True)
    )

    for label in ("safe re-encode", "rescue re-encode"):
        cmd = strategies[label]
        assert _codec_of(cmd) == "libx265", (
            f"[video] 10-bit HEVC strategy '{label}' must encode with libx265."
        )
        assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p10le", (
            f"[video] 10-bit HEVC strategy '{label}' must preserve yuv420p10le pixel format."
        )

    fallback = strategies["h264 fallback"]
    assert fallback[fallback.index("-pix_fmt") + 1] == "yuv420p", (
        "[video] H.264 fallback strategy must convert 10-bit input to 8-bit yuv420p."
    )


def test_hevc_mkv_strategies_all_use_x265_including_subtitles_one():
    """Verifies MKV HEVC strategies keep subtitles, omit hvc1 tag, and append H.264 fallback."""
    strategies = dict(_strategies("mkv", codec="hevc", hevc_available=True))

    assert "re-encode keeping subtitles" in strategies, (
        "[video] MKV HEVC strategy list must include subtitle-preserving first attempt."
    )
    for label in (
        "re-encode keeping subtitles",
        "safe re-encode",
        "rescue re-encode",
    ):
        assert _codec_of(strategies[label]) == "libx265", (
            f"[video] MKV HEVC strategy '{label}' must use libx265."
        )
        assert "-tag:v" not in strategies[label], (
            f"[video] MKV strategy '{label}' must not inject MP4/MOV-specific '-tag:v hvc1'."
        )
    assert _codec_of(strategies["h264 fallback"]) == "libx264", (
        "[video] MKV HEVC final fallback strategy must use libx264."
    )


@pytest.mark.parametrize(
    "ext,codec,available",
    [
        ("mp4", "h264", True),
        ("mp4", None, True),  # probe failed
        ("mp4", "vp9", True),
        ("mp4", "hevc", False),  # libx265 missing in the binary
        ("avi", "hevc", True),  # container not eligible
        ("webm", "hevc", True),
        ("wmv", "hevc", True),
    ],
)
def test_non_hevc_path_is_exactly_the_original(ext, codec, available):
    """No x265, no hvc1 tag and no extra fallback strategy outside the HEVC case."""
    strategies = _strategies(ext, codec=codec, hevc_available=available)
    legacy = vc._build_strategies(FFMPEG, Path("in.mp4"), Path("out.tmp"), ext, 80)

    assert strategies == legacy, (
        f"[video] Non-HEVC strategy list deviated from legacy baseline for ext='{ext}', codec='{codec}'."
    )
    assert all("libx265" not in cmd and "hvc1" not in cmd for _, cmd in strategies), (
        "[video] Non-HEVC strategy list must never reference libx265 or hvc1."
    )
    assert "h264 fallback" not in dict(strategies), (
        "[video] Non-HEVC strategy list must not append an extra 'h264 fallback' entry."
    )


# --- Integration with the real FFmpeg ---


@needs_x265
@pytest.mark.parametrize("ext", ["mp4", "mov", "mkv"])
def test_hevc_source_is_compressed_as_hevc_and_smaller(
    tmp_workspace, create_sample_video, ext
):
    """Acceptance: HEVC in -> HEVC out, smaller than the source at default quality."""
    in_dir, out_dir = tmp_workspace
    src = create_sample_video(
        in_dir / f"phone.{ext}",
        duration_sec=2,
        codec="libx265",
        crf=22,
        size="640x360",
        noisy=True,
    )
    dst = out_dir / f"phone_out.{ext}"

    assert vc.file_compressor(src, dst, quality=80) is True, (
        f"[video] HEVC compression failed for '{ext}' source at quality=80."
    )

    assert probe_streams(get_ffmpeg_path(), dst).video_codec == "hevc", (
        f"[video] Compressed '{ext}' output regressed to non-HEVC codec instead of preserving HEVC."
    )
    assert dst.stat().st_size < src.stat().st_size, (
        f"[video] Compressed HEVC '{ext}' file ({dst.stat().st_size} B) was not smaller than source ({src.stat().st_size} B)."
    )
    if ext in ("mp4", "mov"):
        assert "hvc1" in _video_line(dst), (
            f"[video] Compressed '{ext}' HEVC stream is missing the 'hvc1' fourcc tag."
        )


@needs_x265
def test_h264_source_stays_h264(tmp_workspace, create_sample_video):
    """Regression: an H.264 source is still compressed with libx264."""
    in_dir, out_dir = tmp_workspace
    src = create_sample_video(
        in_dir / "clip.mp4", duration_sec=2, crf=14, size="640x360", noisy=True
    )
    dst = out_dir / "clip_out.mp4"

    assert vc.file_compressor(src, dst, quality=60) is True, (
        "[video] H.264 source compression unexpectedly failed."
    )

    assert probe_streams(get_ffmpeg_path(), dst).video_codec == "h264", (
        "[video] H.264 source must remain encoded as h264 rather than switching to HEVC."
    )
    assert dst.stat().st_size <= src.stat().st_size, (
        "[video] Compressed H.264 output exceeded original source file size."
    )


@needs_x265
def test_hevc_source_falls_back_to_h264_when_encoder_is_missing(
    tmp_workspace, create_sample_video, monkeypatch
):
    """A binary without libx265 must behave like before, never fail."""
    in_dir, out_dir = tmp_workspace
    src = create_sample_video(
        in_dir / "phone.mp4",
        duration_sec=2,
        codec="libx265",
        crf=22,
        size="640x360",
        noisy=True,
    )
    dst = out_dir / "phone_out.mp4"

    monkeypatch.setattr(vc, "has_encoder", lambda *_a, **_k: False)

    assert vc.file_compressor(src, dst, quality=80) is True, (
        "[video] HEVC compression must succeed via H.264 fallback when libx265 is unavailable."
    )
    assert dst.exists(), (
        "[video] Fallback H.264 output file was not written when libx265 was disabled."
    )
    assert probe_streams(get_ffmpeg_path(), dst).video_codec in ("h264", "hevc"), (
        "[video] Probed fallback output must contain a valid h264 or kept hevc video stream."
    )
    # With x265 disabled the encoder used must be x264 (or the original is kept).
    if dst.read_bytes() != src.read_bytes():
        assert probe_streams(get_ffmpeg_path(), dst).video_codec == "h264", (
            "[video] Re-encoded fallback output with libx265 disabled must use h264."
        )


@needs_x265
def test_hevc_failure_in_x265_strategies_uses_h264_fallback(
    tmp_workspace, create_sample_video, monkeypatch
):
    """If every libx265 strategy fails, the final libx264 strategy still produces output."""
    in_dir, out_dir = tmp_workspace
    src = create_sample_video(
        in_dir / "phone.mp4",
        duration_sec=2,
        codec="libx265",
        crf=22,
        size="640x360",
        noisy=True,
    )
    dst = out_dir / "phone_out.mp4"

    original_build = vc._build_strategies

    def broken_x265(*args, **kwargs):
        strategies = original_build(*args, **kwargs)
        broken = []
        for label, cmd in strategies:
            if "libx265" in cmd:
                cmd = list(cmd)
                cmd[cmd.index("-c:v") + 1] = "encoder_that_does_not_exist"
            broken.append((label, cmd))
        return broken

    monkeypatch.setattr(vc, "_build_strategies", broken_x265)

    assert vc.file_compressor(src, dst, quality=80) is True, (
        "[video] Compression must recover via the trailing libx264 strategy when all libx265 commands fail."
    )
    assert dst.exists() and dst.stat().st_size > 0, (
        "[video] H.264 rescue fallback did not produce a non-empty output file."
    )
    assert list(out_dir.glob(".*_tmp_*")) == [], (
        "[video] Failed libx265 attempts leaked temporary files after H.264 fallback succeeded."
    )


def test_corrupted_source_still_fails_cleanly(tmp_path):
    """Probe failure (no codec detected) keeps the old behavior: False, no output."""
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"NOT_A_VALID_MEDIA_HEADER")
    out = tmp_path / "out.mp4"

    assert vc.file_compressor(bad, out, quality=80) is False, (
        "[video] Corrupted media file with unprobeable streams must return False cleanly."
    )
    assert not out.exists(), (
        "[video] Failed compression of corrupted source must not leave behind an output file."
    )
