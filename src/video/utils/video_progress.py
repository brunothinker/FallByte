import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class VideoProgressInfo:
    current_file_index: int
    total_files: int
    start_time: float
    file_path: Optional[Path] = None
    duration_seconds: float = 0.0
    processed_seconds: float = 0.0
    fps: float = 0.0
    speed: str = "1x"
    success: bool = True
    orig_bytes: int = 0
    comp_bytes: int = 0

    @property
    def file_percentage(self) -> float:
        """Percentage of overall batch queue completion."""
        if self.total_files == 0:
            return 0.0
        return round((self.current_file_index / self.total_files) * 100, 1)

    @property
    def current_video_percentage(self) -> float:
        """Percentage of processing completion for the active video file."""
        if self.duration_seconds <= 0.0:
            return 0.0
        pct = (self.processed_seconds / self.duration_seconds) * 100
        return round(min(pct, 100.0), 1)

    @property
    def elapsed_seconds(self) -> float:
        """Total execution time in seconds since the session started."""
        return round(time.perf_counter() - self.start_time, 2)

    @property
    def estimated_remaining_seconds(self) -> float:
        """Estimates remaining batch time based on processed files average duration."""
        if self.current_file_index == 0:
            return 0.0
        avg_time_per_file = self.elapsed_seconds / self.current_file_index
        remaining_files = self.total_files - self.current_file_index
        return round(avg_time_per_file * remaining_files, 1)

    @property
    def space_saved_percentage(self) -> float:
        """Calculates percentage of storage space saved after compression."""
        if self.orig_bytes <= 0:
            return 0.0
        saved = self.orig_bytes - self.comp_bytes
        return round((saved / self.orig_bytes) * 100, 1)