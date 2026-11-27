"""Shared FFmpeg media track probing primitives for audio and video engines."""

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

_TRACK_STREAM_RE = re.compile(
    r"^\s*Stream #0:(\d+)(?:\[[^\]]+\])?(?:\(([^)]+)\))?:\s*(Audio|Subtitle|Data):\s*([^\r\n]+)"
)
_METADATA_KV_RE = re.compile(r"^\s*([a-zA-Z0-9_-]+)\s*:\s*(.+)$")


def _subprocess_kwargs() -> dict:
    """Common subprocess options: no stdin, captured output, no console flash on Windows."""
    kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


@dataclass(frozen=True)
class MediaTrack:
    """Represents an embedded audio or subtitle stream in a video container."""

    stream_index: int
    track_type: Literal["audio", "subtitle"]
    codec: str
    language: str | None = None
    title: str | None = None
    details: str | None = None
    is_default: bool = False
    is_forced: bool = False

    def display_label(self) -> str:
        """Builds a clean, human-readable label for the UI without raw FFmpeg syntax."""
        parts: list[str] = []

        if self.language and self.language.lower() != "und":
            parts.append(self.language.upper())
        else:
            parts.append("Unknown Language")

        if self.title:
            parts.append(f'"{self.title}"')

        meta_badges: list[str] = [self.codec.upper()]
        if self.details:
            meta_badges.append(self.details)
        if self.is_default:
            meta_badges.append("Default")
        if self.is_forced:
            meta_badges.append("Forced")

        parts.append(f"[{', '.join(meta_badges)}]")
        return " — ".join(parts)


def _extract_track_details(raw_desc: str, track_type: str) -> str | None:
    """Extracts human-friendly channel layout or descriptor from a stream line."""
    cleaned = re.sub(
        r"\((?:default|forced|dub|original|comment|hearing impaired|visual impaired)\)",
        "",
        raw_desc,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\[[^\]]+\]", "", cleaned)
    tokens = [t.strip() for t in cleaned.split(",") if t.strip()]

    if track_type == "audio" and len(tokens) >= 3:
        channel_token = tokens[2].split("(")[0].strip()
        if (
            channel_token
            and not channel_token.endswith("Hz")
            and "kb/s" not in channel_token
        ):
            return channel_token
    return None


def parse_media_tracks_stderr(
    stderr_text: str,
) -> tuple[list[MediaTrack], list[MediaTrack]]:
    """Parses embedded audio and subtitle tracks (including metadata titles) from `ffmpeg -i` stderr.

    Supports all container formats (MKV, WebM, MP4, MOV, M4V, 3GP, TS, MPG, AVI, FLV, WMV),
    including composite language tags (e.g., `(por, hearing impaired)`) and MP4 subtitle
    tracks stored as `Data: bin_data (text / ...)` with `handler_name: SubtitleHandler`.

    Returns:
        tuple[list[MediaTrack], list[MediaTrack]]: (audio_tracks, subtitle_tracks)
    """
    audio_tracks: list[MediaTrack] = []
    subtitle_tracks: list[MediaTrack] = []

    raw_tracks: list[dict] = []
    current_track: dict | None = None
    in_metadata = False

    for line in stderr_text.splitlines():
        stream_match = _TRACK_STREAM_RE.match(line)
        if stream_match:
            if current_track is not None:
                raw_tracks.append(current_track)

            idx_str, raw_lang, kind, rest = stream_match.groups()
            lang = raw_lang.split(",")[0].strip() if raw_lang else None
            codec_token = rest.split(",")[0].split("(")[0].split("[")[0].strip().lower()

            if kind == "Audio":
                track_kind: Literal["audio", "subtitle"] = "audio"
                is_confirmed = True
            elif kind == "Subtitle":
                track_kind = "subtitle"
                is_confirmed = True
            else:
                track_kind = "subtitle"
                is_confirmed = "(text /" in rest.lower()

            current_track = {
                "stream_index": int(idx_str),
                "track_type": track_kind,
                "codec": "text" if codec_token == "bin_data" else codec_token,
                "language": lang if lang else None,
                "title": None,
                "details": _extract_track_details(rest, track_kind),
                "is_default": "(default)" in rest.lower(),
                "is_forced": "(forced)" in rest.lower(),
                "_confirmed": is_confirmed,
            }
            in_metadata = False
            continue

        if line.lstrip().startswith("Stream #"):
            if current_track is not None:
                raw_tracks.append(current_track)
                current_track = None
            in_metadata = False
            continue

        if current_track is not None:
            stripped = line.strip()
            if stripped == "Metadata:":
                in_metadata = True
                continue

            if in_metadata:
                if line.startswith("      ") or line.startswith("\t\t"):
                    kv_match = _METADATA_KV_RE.match(stripped)
                    if kv_match:
                        key, val = kv_match.group(1).lower(), kv_match.group(2).strip()
                        if key == "title" and val:
                            current_track["title"] = val
                        elif key == "language" and not current_track["language"] and val:
                            current_track["language"] = val.split(",")[0].strip()
                        elif key == "handler_name":
                            lower_val = val.lower()
                            if "subtitle" in lower_val:
                                current_track["_confirmed"] = True
                            elif "chapter" in lower_val or "timecode" in lower_val:
                                current_track["_confirmed"] = False
                else:
                    in_metadata = False

    if current_track is not None:
        raw_tracks.append(current_track)

    for item in raw_tracks:
        if not item.pop("_confirmed", True):
            continue
        track = MediaTrack(**item)
        if track.track_type == "audio":
            audio_tracks.append(track)
        else:
            subtitle_tracks.append(track)

    return audio_tracks, subtitle_tracks


def probe_media_tracks(
    ffmpeg_bin: Path, input_path: Path
) -> tuple[list[MediaTrack], list[MediaTrack]]:
    """Inspects a media file and returns its embedded (audio_tracks, subtitle_tracks).

    Never raises; returns empty lists if probing fails.
    """
    try:
        result = subprocess.run(
            [str(ffmpeg_bin), "-hide_banner", "-i", str(input_path)],
            check=False,
            timeout=60,
            **_subprocess_kwargs(),
        )
    except (OSError, subprocess.SubprocessError):
        return [], []

    stderr_text = result.stderr.decode("utf-8", errors="ignore")
    return parse_media_tracks_stderr(stderr_text)
