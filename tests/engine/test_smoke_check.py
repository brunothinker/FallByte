"""Unit tests for the CLI smoke check utility module."""

import sys
from unittest.mock import patch

from src.utils.smoke_check import run_smoke_check


def test_run_smoke_check_success():
    """Validates that run_smoke_check returns True in a fully functional environment."""
    assert run_smoke_check() is True, (
        "Expected run_smoke_check() to return True when all dependencies and binaries are healthy."
    )


def test_run_smoke_check_ffmpeg_missing(monkeypatch):
    """Ensures run_smoke_check returns False when FFmpeg binary lookup fails."""
    def fake_get_ffmpeg_path():
        raise FileNotFoundError("Simulated missing FFmpeg binary")

    monkeypatch.setattr("src.video.utils.binary_manager.get_ffmpeg_path", fake_get_ffmpeg_path)

    stderr_buffer = []
    with patch.object(sys.stderr, "write", side_effect=stderr_buffer.append):
        result = run_smoke_check()

    assert result is False, (
        "Expected run_smoke_check() to return False when FFmpeg binary is missing."
    )
    assert any("Smoke check failed" in line for line in stderr_buffer), (
        "Expected failure diagnostic message to be written to stderr when FFmpeg is missing."
    )


def test_run_smoke_check_image_save_failure(monkeypatch):
    """Ensures run_smoke_check returns False when PIL image conversion raises an exception."""
    def fake_save(*args, **kwargs):
        raise OSError("Simulated encoding failure")

    monkeypatch.setattr("PIL.Image.Image.save", fake_save)

    stderr_buffer = []
    with patch.object(sys.stderr, "write", side_effect=stderr_buffer.append):
        result = run_smoke_check()

    assert result is False, (
        "Expected run_smoke_check() to return False when image encoding raises an exception."
    )
    assert any("Simulated encoding failure" in line for line in stderr_buffer), (
        "Expected exception details to be written to stderr on image encoding failure."
    )


def test_run_smoke_check_failure_when_stderr_is_none(monkeypatch, caplog):
    """Ensures run_smoke_check handles failure gracefully without AttributeError on windowed builds (sys.stderr=None)."""
    def fake_get_ffmpeg_path():
        raise FileNotFoundError("Simulated missing FFmpeg in windowed mode")

    monkeypatch.setattr("src.video.utils.binary_manager.get_ffmpeg_path", fake_get_ffmpeg_path)
    monkeypatch.setattr(sys, "stderr", None)

    with caplog.at_level("ERROR", logger="src.utils.smoke_check"):
        result = run_smoke_check()

    assert result is False, (
        "Expected run_smoke_check() to return False cleanly when sys.stderr is None."
    )
    assert any(
        "Simulated missing FFmpeg in windowed mode" in rec.getMessage()
        for rec in caplog.records
    ), (
        "Windowed-build regression: failure diagnostic was not routed to logger.error when sys.stderr is None."
    )