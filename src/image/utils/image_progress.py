import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProgressInfo:
    """Data structure holding execution progress metadata and performance metrics.

    Attributes:
        current (int): Index of the current file being processed (1-based).
        total (int): Total count of files in the batch operation.
        start_time (float): Reference timestamp (`time.perf_counter()`) marking task start.
        file_path (Path | None, optional): Path to the active file being processed. Defaults to None.
        success (bool, optional): Indicates whether current item execution succeeded. Defaults to True.
        orig_bytes (int, optional): Source file size in bytes. Defaults to 0.
        comp_bytes (int, optional): Resulting output file size in bytes. Defaults to 0.
    """

    current: int
    total: int
    start_time: float
    file_path: Path | None = None
    success: bool = True
    orig_bytes: int = 0
    comp_bytes: int = 0

    @property
    def percentage(self) -> float:
        """Calculates completed batch progress as a rounded percentage (0.0 - 100.0)."""
        if self.total == 0:
            return 0.0
        return round((self.current / self.total) * 100, 1)

    @property
    def elapsed_seconds(self) -> float:
        """Calculates total wall-clock duration elapsed since execution start."""
        return round(time.perf_counter() - self.start_time, 2)

    @property
    def estimated_remaining_seconds(self) -> float:
        """Estimates remaining execution time based on current average throughput speed."""
        if self.current == 0:
            return 0.0
        avg_time = self.elapsed_seconds / self.current
        remaining = self.total - self.current
        return round(avg_time * remaining, 1)