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
    return [
        h
        for h in logging.getLogger().handlers
        if (h.name or "").startswith("fallbyte_")
    ]


def test_setup_logging_creates_file_and_captures_info(isolated_logging):
    log_file = main.setup_logging()

    assert log_file == isolated_logging
    assert logging.getLogger().level == logging.INFO

    logging.getLogger("test").info("hello info")
    for handler in _fallbyte_handlers():
        handler.flush()
    assert "hello info" in log_file.read_text(encoding="utf-8")


def test_setup_logging_twice_does_not_duplicate_handlers(isolated_logging):
    main.setup_logging()
    first = _fallbyte_handlers()
    assert first

    main.setup_logging()
    assert _fallbyte_handlers() == first


def test_setup_logging_debug_enables_debug_level(isolated_logging):
    main.setup_logging(debug=True)
    assert logging.getLogger().level == logging.DEBUG


def test_setup_logging_without_stderr(isolated_logging, monkeypatch):
    monkeypatch.setattr(sys, "stderr", None)

    log_file = main.setup_logging()

    handlers = _fallbyte_handlers()
    assert len(handlers) == 1
    assert isinstance(handlers[0], logging.FileHandler)
    logging.getLogger("test").info("file only")
    handlers[0].flush()
    assert "file only" in log_file.read_text(encoding="utf-8")
