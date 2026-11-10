"""Centralized execution progress data structures for FallByte engines and controllers."""

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
        duration_seconds (float, optional): Total duration of the active media file in seconds. Defaults to 0.0.
        processed_seconds (float, optional): Duration already processed by FFmpeg in seconds. Defaults to 0.0.
        fps (float, optional): Current encoding framerate from FFmpeg. Defaults to 0.0.
        speed (float, optional): Encoding speed multiplier relative to realtime (e.g. 1.5x). Defaults to 0.0.
    """

    current: int
    total: int
    start_time: float
    file_path: Path | None = None
    success: bool = True
    orig_bytes: int = 0
    comp_bytes: int = 0
    duration_seconds: float = 0.0
    processed_seconds: float = 0.0
    fps: float = 0.0
    speed: float = 0.0

    @property
    def item_percentage(self) -> float:
        """Calculates progress percentage for the active single file (0.0 - 100.0)."""
        if self.duration_seconds <= 0.0:
            return 0.0
        pct = (self.processed_seconds / self.duration_seconds) * 100.0
        return min(100.0, max(0.0, round(pct, 1)))

    @property
    def percentage(self) -> float:
        """Calculates completed batch progress as a rounded percentage (0.0 - 100.0),

        incorporating intra-file partial progress for smooth progress bar updates.
        """
        if self.total == 0:
            return 0.0
        active_idx = max(0, self.current - 1)
        active_item_fraction = (
            self.item_percentage / 100.0 if self.duration_seconds > 0.0 else 0.0
        )
        overall_progress = (active_idx + active_item_fraction) / self.total
        return min(100.0, max(0.0, round(overall_progress * 100.0, 1)))

    @property
    def elapsed_seconds(self) -> float:
        """Calculates total wall-clock duration elapsed since execution start."""
        return round(time.perf_counter() - self.start_time, 2)

    @property
    def estimated_remaining_seconds(self) -> float:
        """Estimates remaining execution time based on current item speed or average batch throughput."""
        if self.duration_seconds > 0.0 and self.speed > 0.0:
            remaining_item_sec = max(
                0.0, self.duration_seconds - self.processed_seconds
            )
            return round(remaining_item_sec / self.speed, 1)

        if self.current == 0:
            return 0.0
        avg_time = self.elapsed_seconds / self.current
        remaining = self.total - self.current
        return round(avg_time * remaining, 1)