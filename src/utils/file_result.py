"""Unified per-file result shared by every FallByte engine and controller."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Outcome(Enum):
    """Final state of a single processed file."""

    PROCESSED = "processed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class FileResult:
    """Outcome of processing one file.

    Attributes:
        outcome (Outcome): PROCESSED, SKIPPED (original copied or nothing
            generated) or FAILED.
        reason_key (str | None): Locale key explaining a skip. Only meaningful
            for SKIPPED results.
        reason_params (dict[str, Any]): Format parameters for the locale key.
    """

    outcome: Outcome
    reason_key: str | None = None
    reason_params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def processed(cls) -> "FileResult":
        """File was processed and a new output was generated."""
        return cls(Outcome.PROCESSED)

    @classmethod
    def skipped(cls, reason_key: str, **params: Any) -> "FileResult":
        """File needed no change (original kept) or nothing could be generated."""
        return cls(Outcome.SKIPPED, reason_key, dict(params))

    @classmethod
    def failed(cls) -> "FileResult":
        """File could not be processed."""
        return cls(Outcome.FAILED)

    @property
    def is_processed(self) -> bool:
        return self.outcome is Outcome.PROCESSED

    @property
    def is_skipped(self) -> bool:
        return self.outcome is Outcome.SKIPPED

    @property
    def is_failed(self) -> bool:
        return self.outcome is Outcome.FAILED

    def __bool__(self) -> bool:
        """True when the file did not fail.

        Bridge that keeps legacy ``bool`` callers working. Removed in Stage 6.
        """
        return not self.is_failed


def as_file_result(value: "bool | FileResult") -> FileResult:
    """Normalizes a legacy ``bool`` or a ``FileResult`` into a ``FileResult``.

    Bridge for engines not yet migrated. Removed (``bool`` support) in Stage 6.
    """
    if isinstance(value, FileResult):
        return value
    return FileResult.processed() if value else FileResult.failed()
