"""HEVC compression tests: the output codec follows a HEVC source.

Pins three things:
  * HEVC sources (mp4/mov/mkv) are compressed with libx265 and keep the hvc1 tag;
  * every other source keeps the original libx264/VP9/WMV2 behavior (regression);
  * if libx265 is missing or fails, compression falls back to the old H.264 path.

Integration tests need the bundled FFmpeg with libx265 and are skipped otherwise.
"""

import subprocess
from pathlib import Path

import pytest

from src.video import video_file_compression as vc
from src.video.utils import ffmpeg_utils
from src.video.utils.binary_manager import get_ffmpeg_path
from src.video.utils.ffmpeg_utils import get_codec_args, probe_streams

FFMPEG = Path("ffmpeg")


def _codec_of(args: list[str]) -> str:
    return args[args.index("-c:v") + 1]


def _crf_of(args: list[str]) -> int:
    return int(args[args.index("-crf") + 1])


def _strategies(ext, quality=80, codec=None, hevc_available=False):
    return vc._build_strategies(
        FFMPEG, Path("in.mp4"), Path("out.tmp"), ext, quality, codec, hevc_available
    )


def _video_line(path: Path) -> str:
    """Returns the `Video:` line printed by `ffmpeg -i` (shows codec and tag)."""
    result = subprocess.run(
        [str(get_ffmpeg_path()), "-hide_banner", "-i", str(path)],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    for line in result.stderr.decode("utf-8", errors="ignore").splitlines():
        if "Video:" in line:
            return line
    return ""


needs_x265 = pytest.mark.skipif(
    not ffmpeg_utils.has_encoder(get_ffmpeg_path(), "libx265"),
    reason="bundled FFmpeg has no libx265",
)


# --- get_codec_args: unit ---


def test_conversion_defaults_are_unchanged():
    """Conversion calls (no quality) must never be affected by the HEVC path."""
    assert get_codec_args("mp4") == ["-c:v", "libx264", "-c:a", "aac"]
    assert get_codec_args("mp4", None, "hevc") == ["-c:v", "libx264", "-c:a", "aac"]


@pytest.mark.parametrize("ext", ["mp4", "mov", "mkv", "avi"])
@pytest.mark.parametrize("quality", [1, 30, 60, 80, 100])
def test_h264_compression_args_are_unchanged(ext, quality):
    """Regression: without a HEVC source the CRF mapping is the original one."""
    expected_crf = round(18 + (100 - quality) * 0.22)
    for codec in (None, "h264", "vp9", "av1"):
        args = get_codec_args(ext, quality, codec)
        assert _codec_of(args) == "libx264"
        assert _crf_of(args) == expected_crf


@pytest.mark.parametrize("ext", ["mp4", "mov", "mkv"])
def test_hevc_compression_uses_libx265(ext):
    args = get_codec_args(ext, 80, "hevc")
    assert _codec_of(args) == "libx265"
    assert _crf_of(args) == round(23 + (100 - 80) * 0.22)


@pytest.mark.parametrize(
    "ext,expected",
    [("avi", "libx264"), ("webm", "libvpx-vp9"), ("wmv", "wmv2")],
)
def test_hevc_in_other_containers_keeps_container_codec(ext, expected):
    assert _codec_of(get_codec_args(ext, 80, "hevc")) == expected


def test_hevc_quality_slider_is_monotonic_and_within_range():
    """Lower quality -> higher CRF, same slope as x264, always valid for x265 (0-51)."""
    crfs = [_crf_of(get_codec_args("mp4", q, "hevc")) for q in range(1, 101)]
    assert crfs == sorted(crfs, reverse=True)
    assert all(0 <= c <= 51 for c in crfs)
    h264 = [_crf_of(get_codec_args("mp4", q)) for q in range(1, 101)]
    assert {x - h for x, h in zip(crfs, h264)} <= {4, 5, 6}  # offset ~5 (+rounding)


# --- _build_strategies: unit ---


@pytest.mark.parametrize("ext", ["mp4", "mov"])
def test_hevc_strategies_tag_hvc1_and_fall_back_to_h264(ext):
    strategies = dict(_strategies(ext, codec="hevc", hevc_available=True))

    for label in ("safe re-encode", "rescue re-encode"):
        cmd = strategies[label]
        assert _codec_of(cmd) == "libx265"
        assert cmd[cmd.index("-tag:v") + 1] == "hvc1"

    fallback = strategies["h264 fallback"]
    assert _codec_of(fallback) == "libx264"
    assert "-tag:v" not in fallback
    assert list(strategies)[-1] == "h264 fallback"


def test_hevc_mkv_strategies_all_use_x265_including_subtitles_one():
    strategies = dict(_strategies("mkv", codec="hevc", hevc_available=True))

    assert "re-encode keeping subtitles" in strategies
    for label in (
        "re-encode keeping subtitles",
        "safe re-encode",
        "rescue re-encode",
    ):
        assert _codec_of(strategies[label]) == "libx265"
        assert "-tag:v" not in strategies[label]  # tag is MP4/MOV only
    assert _codec_of(strategies["h264 fallback"]) == "libx264"


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
    legacy = vc._build_strategies(
        FFMPEG, Path("in.mp4"), Path("out.tmp"), ext, 80
    )

    assert strategies == legacy
    assert all("libx265" not in cmd and "hvc1" not in cmd for _, cmd in strategies)
    assert "h264 fallback" not in dict(strategies)


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

    assert vc.file_compressor(src, dst, quality=80) is True

    assert probe_streams(get_ffmpeg_path(), dst).video_codec == "hevc"
    assert dst.stat().st_size < src.stat().st_size
    if ext in ("mp4", "mov"):
        assert "hvc1" in _video_line(dst)


@needs_x265
def test_h264_source_stays_h264(tmp_workspace, create_sample_video):
    """Regression: an H.264 source is still compressed with libx264."""
    in_dir, out_dir = tmp_workspace
    src = create_sample_video(
        in_dir / "clip.mp4", duration_sec=2, crf=14, size="640x360", noisy=True
    )
    dst = out_dir / "clip_out.mp4"

    assert vc.file_compressor(src, dst, quality=60) is True

    assert probe_streams(get_ffmpeg_path(), dst).video_codec == "h264"
    assert dst.stat().st_size <= src.stat().st_size


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

    assert vc.file_compressor(src, dst, quality=80) is True
    assert dst.exists()
    assert probe_streams(get_ffmpeg_path(), dst).video_codec in ("h264", "hevc")
    # With x265 disabled the encoder used must be x264 (or the original is kept).
    if dst.read_bytes() != src.read_bytes():
        assert probe_streams(get_ffmpeg_path(), dst).video_codec == "h264"


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

    assert vc.file_compressor(src, dst, quality=80) is True
    assert dst.exists() and dst.stat().st_size > 0
    assert list(out_dir.glob(".*_tmp_*")) == []


def test_corrupted_source_still_fails_cleanly(tmp_path):
    """Probe failure (no codec detected) keeps the old behavior: False, no output."""
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"NOT_A_VALID_MEDIA_HEADER")
    out = tmp_path / "out.mp4"

    assert vc.file_compressor(bad, out, quality=80) is False
    assert not out.exists()