import logging
import sys


class TextRedirector(logging.Handler):
    """Redirects sys.stdout, sys.stderr and Python logging streams to accumulate console logs in a buffer."""

    def __init__(self) -> None:
        """Initializes buffer and reference variables for standard streams and logger."""
        super().__init__()
        self._buffer: list[str] = []
        self._stdout = sys.stdout
        self._stderr = sys.stderr

    def write(self, message: str) -> None:
        """Writes a message to the buffer and forwards it to the original stdout stream.

        Args:
            message: The string message to write to the console stream.
        """
        if message:
            self._buffer.append(message)
            self._stdout.write(message)

    def flush(self) -> None:
        """Flushes the original stdout stream buffer."""
        self._stdout.flush()

    def emit(self, record: logging.LogRecord) -> None:
        """Captures Python logging module records into the internal buffer.

        Args:
            record: The LogRecord instance emitted by the logging system.
        """
        try:
            msg = self.format(record)
            self._buffer.append(f"[{record.levelname}] {msg}\n")
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

    def get_logs(self) -> str:
        """Returns accumulated console output as a single string.

        Returns:
            A single joined string containing all buffered console logs.
        """
        return "".join(self._buffer)