"""Unit tests for platform-specific bundled FFmpeg binary resolution."""

from pathlib import Path

import pytest

from src.utils import binary_manager


def test_binary_manager_resolves_linux_and_windows(tmp_path: Path, monkeypatch):
    """`get_ffmpeg_path` must resolve OS-specific paths, chmod +x on Linux, and validate existence."""
    fake_root = tmp_path / "repo"
    linux_bin = fake_root / "resources" / "bin" / "linux" / "ffmpeg"
    win_bin = fake_root / "resources" / "bin" / "windows" / "ffmpeg.exe"
    linux_bin.parent.mkdir(parents=True)
    win_bin.parent.mkdir(parents=True)
    linux_bin.write_bytes(b"#!/bin/sh\n")
    linux_bin.chmod(0o644)
    win_bin.write_bytes(b"MZ")

    fake_module_file = fake_root / "src" / "utils" / "binary_manager.py"
    fake_module_file.parent.mkdir(parents=True)
    monkeypatch.setattr(binary_manager, "__file__", str(fake_module_file))

    monkeypatch.setattr(binary_manager.platform, "system", lambda: "Linux")
    resolved_linux = binary_manager.get_ffmpeg_path()
    assert resolved_linux == linux_bin, (
        f"[binary] Expected Linux FFmpeg path '{linux_bin}', got '{resolved_linux}'."
    )
    assert resolved_linux.stat().st_mode & 0o111, (
        "[binary] Expected `get_ffmpeg_path` to grant execute permission (+x) on Linux."
    )

    monkeypatch.setattr(binary_manager.platform, "system", lambda: "Windows")
    resolved_win = binary_manager.get_ffmpeg_path()
    assert resolved_win == win_bin, (
        f"[binary] Expected Windows FFmpeg path '{win_bin}', got '{resolved_win}'."
    )

    monkeypatch.setattr(binary_manager.platform, "system", lambda: "Darwin")
    with pytest.raises(OSError, match="Unsupported operating system"):
        binary_manager.get_ffmpeg_path()

    linux_bin.unlink()
    monkeypatch.setattr(binary_manager.platform, "system", lambda: "Linux")
    with pytest.raises(FileNotFoundError, match="FFmpeg binary not found"):
        binary_manager.get_ffmpeg_path()