"""Batch progress bar must reflect completed files, not started files.

The bar value is computed exactly as in `BaseController._run_batch_directory_job`:
`progress_bar.value = info.percentage / 100.0`.
"""

import time
from pathlib import Path

import pytest

from src.utils.progress import ProgressInfo


def _emit_like_run_batch(total: int) -> list[tuple[ProgressInfo, float]]:
    """Mimics run_batch for image files (duration_seconds == 0): a start
    event (is_completed=False) and a completion event per file.
    Returns each event with the bar value the controller would show."""
    t0 = time.perf_counter()
    events: list[tuple[ProgressInfo, float]] = []
    for index in range(1, total + 1):
        path = Path(f"img_{index}.png")
        start = ProgressInfo(
            current=index, total=total, start_time=t0, file_path=path, is_completed=False
        )
        events.append((start, start.percentage / 100.0))
        done = ProgressInfo(
            current=index, total=total, start_time=t0, file_path=path, is_completed=True
        )
        events.append((done, done.percentage / 100.0))
    return events


@pytest.mark.parametrize("total", [1, 2, 3, 7])
def test_bar_is_zero_before_first_image_completes(total: int) -> None:
    events = _emit_like_run_batch(total)
    first_completed = next(i for i, (e, _) in enumerate(events) if e.is_completed)
    assert all(bar == 0.0 for _, bar in events[:first_completed])


@pytest.mark.parametrize("total", [1, 2, 3, 7])
def test_bar_reaches_one_only_after_last_image_completes(total: int) -> None:
    events = _emit_like_run_batch(total)
    last_start_bar = events[-2][1]
    final_bar = events[-1][1]
    assert last_start_bar < 1.0
    assert final_bar == 1.0
    assert all(bar < 1.0 for _, bar in events[:-1])


def test_bar_is_monotonic_and_tracks_completed_files() -> None:
    total = 4
    events = _emit_like_run_batch(total)
    bars = [bar for _, bar in events]
    assert bars == sorted(bars)
    for event, bar in events:
        completed = event.current if event.is_completed else event.current - 1
        assert bar == pytest.approx(completed / total, abs=0.001)


def test_old_formula_would_have_failed() -> None:
    """Regression guard: `current / total` shows 1/N at the first file start."""
    start = ProgressInfo(current=1, total=3, start_time=0.0, is_completed=False)
    assert start.current / start.total > 0.0
    assert start.percentage / 100.0 == 0.0
