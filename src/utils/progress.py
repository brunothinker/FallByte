import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ProgressInfo:
    current: int
    total: int
    start_time: float
    file_path: Optional[Path] = None
    success: bool = True
    orig_bytes: int = 0
    comp_bytes: int = 0

    @property
    def percentage(self) -> float:
        if self.total == 0:
            return 0.0
        return round((self.current / self.total) * 100, 1)

    @property
    def elapsed_seconds(self) -> float:
        return round(time.perf_counter() - self.start_time, 2)

    @property
    def estimated_remaining_seconds(self) -> float:
        if self.current == 0:
            return 0.0
        avg_time = self.elapsed_seconds / self.current
        remaining = self.total - self.current
        return round(avg_time * remaining, 1)