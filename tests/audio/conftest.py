"""Shared fixtures for the audio engine test suite (`tests/audio/`)."""

import subprocess
from pathlib import Path

import pytest

from src.utils import binary_manager
from tests.audio.helpers import skip_if_format_encoders_unavailable


@pytest.fixture
def sample_audio_factory(tmp_path: Path):
    """Generates real audio files using the bundled FFmpeg `lavfi` sine source."""
    ffmpeg_bin = binary_manager.get_ffmpeg_path()

    def _create(
        filename: str = "sample.wav",
        duration: float = 1.5,
        frequency: int = 440,
        bitrate: str | None = None,
        channels: int = 2,
        with_cover_art: bool = False,
    ) -> Path:
        out_path = tmp_path / filename
        out_path.parent.mkdir(parents=True, exist_ok=True)
        ext = out_path.suffix.lower().lstrip(".")
        skip_if_format_encoders_unavailable(ext)

        cmd = [
            str(ffmpeg_bin),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:sample_rate=44100:duration={duration}",
        ]

        if with_cover_art:
            cmd.extend(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c=blue:s=32x32:d={duration}",
                    "-map",
                    "0:a:0",
                    "-map",
                    "1:v:0",
                    "-disposition:v:0",
                    "attached_pic",
                ]
            )

        cmd.extend(["-ac", str(channels)])

        if ext == "mp3":
            cmd.extend(["-c:a", "libmp3lame", "-b:a", bitrate or "192k"])
        elif ext == "m4a":
            cmd.extend(["-c:a", "aac", "-b:a", bitrate or "192k"])
        elif ext == "opus":
            cmd.extend(["-c:a", "libopus", "-b:a", bitrate or "128k", "-ar", "48000"])
        elif ext == "ogg":
            cmd.extend(["-c:a", "libvorbis", "-b:a", bitrate or "192k"])
        elif ext == "flac":
            cmd.extend(["-c:a", "flac"])
        elif ext == "wav":
            cmd.extend(["-c:a", "pcm_s16le"])
        elif ext == "aiff":
            cmd.extend(["-c:a", "pcm_s16be"])
        elif ext == "aac":
            cmd.extend(["-c:a", "aac", "-b:a", bitrate or "192k", "-f", "adts"])

        cmd.append(str(out_path))
        subprocess.run(cmd, check=True)
        assert out_path.exists() and out_path.stat().st_size > 0, (
            f"[audio] Fixture failed to generate sample audio at '{out_path}'."
        )
        return out_path

    return _create


@pytest.fixture
def sample_video_factory(tmp_path: Path):
    """Generates real video files (with or without audio streams) via bundled FFmpeg."""
    ffmpeg_bin = binary_manager.get_ffmpeg_path()

    def _create(
        filename: str = "sample.mp4",
        duration: float = 1.0,
        with_audio: bool = True,
        channels: int = 2,
    ) -> Path:
        out_path = tmp_path / filename
        out_path.parent.mkdir(parents=True, exist_ok=True)
        ext = out_path.suffix.lower().lstrip(".")

        cmd = [
            str(ffmpeg_bin),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s=64x64:r=10:d={duration}",
        ]

        if with_audio:
            cmd.extend(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    f"sine=frequency=440:sample_rate=44100:duration={duration}",
                    "-ac",
                    str(channels),
                ]
            )

        if ext == "webm":
            cmd.extend(["-c:v", "vp8"])
            if with_audio:
                cmd.extend(["-c:a", "libvorbis"])
        else:
            cmd.extend(["-c:v", "mpeg4", "-q:v", "10"])
            if with_audio:
                cmd.extend(["-c:a", "aac", "-b:a", "128k"])

        cmd.append(str(out_path))
        subprocess.run(cmd, check=True)
        assert out_path.exists() and out_path.stat().st_size > 0, (
            f"[audio] Fixture failed to generate sample video at '{out_path}'."
        )
        return out_path

    return _create
