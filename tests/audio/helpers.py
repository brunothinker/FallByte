"""Shared encoder availability helpers and format constants for audio engine tests."""

import functools
import re
import subprocess

import pytest

from src.utils import binary_manager

ALL_TESTABLE_AUDIO_FORMATS: tuple[str, ...] = (
    "mp3",
    "m4a",
    "aac",
    "ogg",
    "opus",
    "flac",
    "wav",
    "aiff",
)

FORMAT_REQUIRED_ENCODER: dict[str, str | None] = {
    "mp3": "libmp3lame",
    "m4a": "aac",
    "aac": "aac",
    "ogg": "libvorbis",
    "opus": "libopus",
    "flac": "flac",
    "wav": "pcm_s16le",
    "aiff": "pcm_s16be",
}


@functools.lru_cache(maxsize=1)
def _available_ffmpeg_encoders() -> frozenset[str]:
    """Queries `ffmpeg -encoders` once per test session and caches available encoder names."""
    try:
        ffmpeg_bin = binary_manager.get_ffmpeg_path()
        result = subprocess.run(
            [str(ffmpeg_bin), "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return frozenset()

    encoders: set[str] = set()
    for line in result.stdout.splitlines():
        match = re.match(r"^\s*[A-Z\.]{6}\s+([a-zA-Z0-9_-]+)\s+", line)
        if match:
            encoders.add(match.group(1))
    return frozenset(encoders)


def has_encoder(encoder_name: str) -> bool:
    """Returns True if the bundled FFmpeg build includes `encoder_name`."""
    return encoder_name in _available_ffmpeg_encoders()


def skip_if_format_encoders_unavailable(*formats: str) -> None:
    """Skips the active test if any required FFmpeg encoder for `formats` is absent."""
    missing = sorted(
        {
            enc
            for fmt in formats
            if (enc := FORMAT_REQUIRED_ENCODER.get(fmt.lower())) is not None
            and not has_encoder(enc)
        }
    )
    if missing:
        pytest.skip(f"Bundled FFmpeg lacks required encoder(s): {', '.join(missing)}")


requires_libmp3lame = pytest.mark.skipif(
    not has_encoder("libmp3lame"),
    reason="Bundled FFmpeg build does not provide 'libmp3lame'.",
)
requires_libvorbis = pytest.mark.skipif(
    not has_encoder("libvorbis"),
    reason="Bundled FFmpeg build does not provide 'libvorbis'.",
)
requires_libopus = pytest.mark.skipif(
    not has_encoder("libopus"),
    reason="Bundled FFmpeg build does not provide 'libopus'.",
)