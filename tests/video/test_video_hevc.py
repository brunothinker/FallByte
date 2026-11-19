"""Regression coverage for converting 10-bit HEVC sources."""

import subprocess
from pathlib import Path

import pytest

from src.video import video_file_conversion as conversion
from src.video.utils.video_ffmpeg_utils import has_encoder, probe_streams


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
    assert conversion.file_converter(source, target, container)
    output = probe_streams(ffmpeg, target)
    assert (output.video_codec, output.pix_fmt) == ("hevc", "yuv420p10le")
