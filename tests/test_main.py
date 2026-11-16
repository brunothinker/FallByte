"""Tests for startup logging configuration in main.setup_logging."""

import logging
import sys

import pytest

import main


@pytest.fixture
def isolated_logging(tmp_path, monkeypatch):
    """Points the log file at a temp dir and restores root logging after."""
    monkeypatch.setattr(main, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(main, "LOG_FILE", tmp_path / "fallbyte.log")

    root = logging.getLogger()
    old_handlers = root.handlers[:]
    old_level = root.level
    for handler in old_handlers:
        root.removeHandler(handler)
    try:
        yield tmp_path / "fallbyte.log"
    finally:
        for handler in root.handlers[:]:
            root.removeHandler(handler)
            handler.close()
        for handler in old_handlers:
            root.addHandler(handler)
        root.setLevel(old_level)


def _fallbyte_handlers():
    """Returns active root logger handlers managed by FallByte."""
    return [
        h
        for h in logging.getLogger().handlers
        if (h.name or "").startswith("fallbyte_")
    ]


def test_setup_logging_creates_file_and_captures_info(isolated_logging):
    """Verifies setup_logging initializes INFO logging and writes records to fallbyte.log."""
    log_file = main.setup_logging()

    assert log_file == isolated_logging, (
        "[main] setup_logging() should return the configured fallbyte.log path inside CONFIG_DIR."
    )
    assert logging.getLogger().level == logging.INFO, (
        "[main] Default root logger level should be INFO when debug=False."
    )

    logging.getLogger("test").info("hello info")
    for handler in _fallbyte_handlers():
        handler.flush()
    assert "hello info" in log_file.read_text(encoding="utf-8"), (
        "[main] Info log records must be flushed and persisted to fallbyte.log."
    )


def test_setup_logging_twice_does_not_duplicate_handlers(isolated_logging):
    """Ensures calling setup_logging repeatedly is idempotent and avoids duplicate handlers."""
    main.setup_logging()
    first = _fallbyte_handlers()
    assert first, (
        "[main] setup_logging() must register fallbyte_ handlers on initial startup."
    )

    main.setup_logging()
    assert _fallbyte_handlers() == first, (
        "[main] Calling setup_logging() multiple times must be idempotent and not duplicate handlers."
    )


def test_setup_logging_debug_enables_debug_level(isolated_logging):
    """Verifies debug=True configures the root logger to emit DEBUG records."""
    main.setup_logging(debug=True)
    assert logging.getLogger().level == logging.DEBUG, (
        "[main] Passing debug=True to setup_logging() must set the root logger level to DEBUG."
    )


def test_setup_logging_without_stderr(isolated_logging, monkeypatch):
    """Ensures windowed builds with sys.stderr=None attach only a FileHandler cleanly."""
    monkeypatch.setattr(sys, "stderr", None)

    log_file = main.setup_logging()

    handlers = _fallbyte_handlers()
    assert len(handlers) == 1, (
        "[main] Windowed builds with sys.stderr=None must only register the FileHandler without a StreamHandler."
    )
    assert isinstance(handlers[0], logging.FileHandler), (
        "[main] The sole registered handler when sys.stderr is None must be a FileHandler."
    )
    logging.getLogger("test").info("file only")
    handlers[0].flush()
    assert "file only" in log_file.read_text(encoding="utf-8"), (
        "[main] File logging must continue recording INFO entries even when sys.stderr is None."
    )