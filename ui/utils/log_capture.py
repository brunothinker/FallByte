import logging
import sys
from dataclasses import dataclass

from src.utils.file_result import LogLevel


@dataclass(frozen=True)
class LogEntry:
    """Structured log entry pairing a semantic level with a rendered message."""

    level: LogLevel
    message: str


class TextRedirector(logging.Handler):
    """Captures structured log entries alongside stdout/stderr and Python logging streams."""

    def __init__(self) -> None:
        """Initializes buffers and stream references."""
        super().__init__()
        self._entries: list[LogEntry] = []
        self._stdout = sys.stdout
        self._stderr = sys.stderr

    def log(self, level: LogLevel, message: str) -> None:
        """Records a structured log line with an explicit semantic level."""
        clean = message.rstrip("\r\n")
        if not clean:
            return
        self._entries.append(LogEntry(level=level, message=clean))
        if self._stdout is not None:
            self._stdout.write(f"{clean}\n")

    def write(self, message: str) -> None:
        """Captures unstructured stdout/stderr writes as INFO entries."""
        if message:
            for line in message.splitlines():
                if line.strip():
                    self._entries.append(LogEntry(level=LogLevel.INFO, message=line))
            if self._stdout is not None:
                self._stdout.write(message)

    def flush(self) -> None:
        """Flushes the original stdout stream buffer when available."""
        if self._stdout is not None:
            self._stdout.flush()

    def emit(self, record: logging.LogRecord) -> None:
        """Captures Python logging records mapped strictly by numeric record level."""
        try:
            msg = self.format(record)
            if record.levelno >= logging.ERROR:
                level = LogLevel.ERROR
            elif record.levelno >= logging.WARNING:
                level = LogLevel.WARNING
            else:
                level = LogLevel.INFO
            self._entries.append(LogEntry(level=level, message=f"[{record.levelname}] {msg}"))
        except Exception:
            self.handleError(record)

    def start(self) -> None:
        """Hijacks sys.stdout, sys.stderr streams and attaches handler to root logger."""
        sys.stdout = self
        sys.stderr = self
        logging.getLogger().addHandler(self)

    def stop(self) -> None:
        """Restores original sys.stdout, sys.stderr streams and detaches logging handler."""
        sys.stdout = self._stdout
        sys.stderr = self._stderr
        logging.getLogger().removeHandler(self)

    def get_entries(self) -> list[LogEntry]:
        """Returns a copy of all accumulated structured log entries."""
        return list(self._entries)

    def get_logs(self) -> str:
        """Returns accumulated console output as a single newline-joined string."""
        return "\n".join(entry.message for entry in self._entries)
