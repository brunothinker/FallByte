"""Tests for audio domain isolation, format constants, and directory scanning."""

import ast
from pathlib import Path

from src.audio.utils import audio_scanner
from src.formats import (
    AUDIO_TARGET_FORMATS,
    SUPPORTED_AUDIO_EXTENSIONS,
    UNCOMPRESSIBLE_AUDIO_FORMATS,
)


def test_audio_module_has_zero_cross_imports_from_video_or_image():
    """Enforces domain isolation: `src/audio/` must never import `src.video` or `src.image`."""
    audio_root = Path(__file__).resolve().parents[2] / "src" / "audio"
    py_files = list(audio_root.rglob("*.py"))
    assert py_files, (
        f"[audio] Expected Python modules under '{audio_root}', found none."
    )

    forbidden_prefixes = ("src.video", "src.image")
    violations: list[str] = []

    for py_file in py_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(forbidden_prefixes):
                        violations.append(f"{py_file.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith(forbidden_prefixes):
                    violations.append(f"{py_file.name}: from {node.module} import ...")

    assert not violations, (
        "[audio] Architectural isolation broken: `src/audio/` imported forbidden domain modules: "
        f"{violations}"
    )


def test_audio_format_constants_consistency():
    """Verifies that target and uncompressible audio formats align with supported extensions."""
    expected_exts = {
        ".mp3",
        ".m4a",
        ".aac",
        ".ogg",
        ".opus",
        ".flac",
        ".wav",
        ".wma",
        ".aiff",
    }
    assert SUPPORTED_AUDIO_EXTENSIONS == expected_exts, (
        f"[audio] SUPPORTED_AUDIO_EXTENSIONS mismatch: got {SUPPORTED_AUDIO_EXTENSIONS}, "
        f"expected {expected_exts}."
    )

    for fmt in AUDIO_TARGET_FORMATS:
        assert f".{fmt}" in SUPPORTED_AUDIO_EXTENSIONS, (
            f"[audio] Target conversion format '{fmt}' is missing from SUPPORTED_AUDIO_EXTENSIONS."
        )

    for fmt_upper in UNCOMPRESSIBLE_AUDIO_FORMATS:
        assert f".{fmt_upper.lower()}" in SUPPORTED_AUDIO_EXTENSIONS, (
            f"[audio] Uncompressible audio format '{fmt_upper}' is not registered in "
            "SUPPORTED_AUDIO_EXTENSIONS."
        )


def test_scan_audio_files_recursive_and_non_recursive(tmp_path: Path):
    """Scanner must find supported audio files case-insensitively and honor `recursive`."""
    (tmp_path / "track_b.MP3").write_bytes(b"fake")
    (tmp_path / "track_a.flac").write_bytes(b"fake")
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")
    (tmp_path / "video.mp4").write_bytes(b"ignore")

    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "nested_c.OpUs").write_bytes(b"fake")

    top_only = audio_scanner.scan_audio_files(tmp_path, recursive=False)
    assert [p.name for p in top_only] == ["track_a.flac", "track_b.MP3"], (
        f"[audio] Non-recursive scan should return only sorted top-level audio files, "
        f"got {[p.name for p in top_only]}."
    )

    all_files = audio_scanner.scan_audio_files(tmp_path, recursive=True)
    assert [p.name for p in all_files] == [
        "nested_c.OpUs",
        "track_a.flac",
        "track_b.MP3",
    ], (
        f"[audio] Recursive scan should return all 3 sorted audio files across subfolders, "
        f"got {[p.name for p in all_files]}."
    )


def test_scan_audio_files_handles_invalid_directory(tmp_path: Path):
    """Scanner must return an empty list without raising for missing paths or regular files."""
    missing = tmp_path / "does_not_exist"
    assert audio_scanner.scan_audio_files(missing) == [], (
        "[audio] Scanning a non-existent directory must safely return an empty list."
    )

    regular_file = tmp_path / "file.mp3"
    regular_file.write_bytes(b"data")
    assert audio_scanner.scan_audio_files(regular_file) == [], (
        "[audio] Scanning a file path instead of a directory must safely return an empty list."
    )
