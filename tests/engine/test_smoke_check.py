"""Unit tests for the CLI smoke check utility module."""

import sys
from unittest.mock import patch

from src.utils.smoke_check import run_smoke_check


def test_run_smoke_check_success():
    """Validates that run_smoke_check returns True in a fully functional environment."""
    assert run_smoke_check() is True


def test_run_smoke_check_ffmpeg_missing(monkeypatch):
    """Ensures run_smoke_check returns False when FFmpeg binary lookup fails."""
    def fake_get_ffmpeg_path():
        raise FileNotFoundError("Simulated missing FFmpeg binary")

    monkeypatch.setattr("src.video.utils.binary_manager.get_ffmpeg_path", fake_get_ffmpeg_path)

    stderr_buffer = []
    with patch.object(sys.stderr, "write", side_effect=stderr_buffer.append):
        result = run_smoke_check()

    assert result is False
    assert any("Smoke check failed" in line for line in stderr_buffer)


def test_run_smoke_check_image_save_failure(monkeypatch):
    """Ensures run_smoke_check returns False when PIL image conversion raises an exception."""
    def fake_save(*args, **kwargs):
        raise OSError("Simulated encoding failure")

    monkeypatch.setattr("PIL.Image.Image.save", fake_save)

    stderr_buffer = []
    with patch.object(sys.stderr, "write", side_effect=stderr_buffer.append):
        result = run_smoke_check()

    assert result is False
    assert any("Simulated encoding failure" in line for line in stderr_buffer)