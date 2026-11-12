"""Unit tests for 10-bit HEVC conversion path in video_file_conversion.

Ensures that when converting 10-bit HEVC sources to MP4/MOV/MKV, the re-encode
strategies use libx265 + yuv420p10le (never libx264 + yuv420p10le).
"""

from pathlib import Path
from unittest.mock import patch

from src.video.video_file_conversion import _build_strategies
from src.video.utils.ffmpeg_utils import has_encoder


def test_10bit_hevc_conversion_uses_consistent_codec_and_pix_fmt():
    """10-bit HEVC to MP4 must not combine libx264 with yuv420p10le."""
    with patch("src.video.video_file_conversion.has_encoder", return_value=True):
        strategies = _build_strategies(
            Path("ffmpeg"),
            Path("in.mp4"),
            Path("out.tmp"),
            "mp4",
            "hevc",
            False,  # video_ok
            True,   # audio_ok
            is_10bit=True,
        )

    reencode_labels = ["safe re-encode", "rescue re-encode"]
    for label, cmd in strategies:
        if label in reencode_labels:
            assert "libx265" in cmd
            assert "yuv420p10le" in cmd
            assert "libx264" not in cmd


def test_10bit_hevc_conversion_falls_back_when_no_x265():
    """Without libx265, 10-bit HEVC conversion should downconvert to 8-bit H.264."""
    with patch("src.video.video_file_conversion.has_encoder", return_value=False):
        strategies = _build_strategies(
            Path("ffmpeg"),
            Path("in.mp4"),
            Path("out.tmp"),
            "mp4",
            "hevc",
            False,
            True,
            is_10bit=True,
        )

    for label, cmd in strategies:
        if "re-encode" in label:
            assert "libx264" in cmd
            assert "yuv420p" in cmd
            assert "yuv420p10le" not in cmd
