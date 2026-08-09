import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProgressInfo:
    """
    Data container representing execution progress and time estimations.

    Attributes:
        current (int): Number of items processed so far.
        total (int): Total number of items to process.
        start_time (float): Timestamp when the process started (time.perf_counter()).
    """
    current: int
    total: int
    start_time: float

    @property
    def percentage(self) -> float:
        """Calculates completed percentage (0.0 to 100.0)."""
        if self.total == 0:
            return 0.0
        return round((self.current / self.total) * 100, 1)

    @property
    def elapsed_seconds(self) -> float:
        """Calculates total elapsed time in seconds since start."""
        return round(time.perf_counter() - self.start_time, 2)

    @property
    def estimated_remaining_seconds(self) -> Optional[float]:
        """
        Estimates remaining time in seconds based on average item processing speed.
        Returns None if no items have been processed yet.
        """
        if self.current == 0:
            return None

        avg_time_per_item = self.elapsed_seconds / self.current
        remaining_items = self.total - self.current
        return round(avg_time_per_item * remaining_items, 1)