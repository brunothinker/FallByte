import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import flet as ft
import pytest
from PIL import Image

from src.video.utils.binary_manager import get_ffmpeg_path

# Add project root directory to sys.path for pytest module resolution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class DummyControl(ft.Control):
    """Dummy control to satisfy component initialization in tests."""


@pytest.fixture
def mock_page():
    """Provides a mocked ft.Page instance for headless UI testing."""
    page = MagicMock()
    page.route = "/"
    page.overlay = []
    page.dialog = None
    return page


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Creates temporary isolated directories for input and output test files."""
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    return input_dir, output_dir


@pytest.fixture
def create_sample_image():
    """Factory fixture to generate sample images with customizable mode and size."""
    def _create(
        path: Path,
        mode: str = "RGB",
        size: tuple[int, int] = (100, 100),
        fmt: str = "PNG",
    ) -> Path:
        img = Image.new(mode, size, color="red" if "RGB" in mode else 128)
        img.save(path, format=fmt)
        return path

    return _create


@pytest.fixture
def create_sample_video():
    """Factory fixture to generate sample synthetic videos using FFmpeg lavfi."""
    def _create(path: Path, duration_sec: int = 1) -> Path:
        ffmpeg_bin = get_ffmpeg_path()
        cmd = [
            str(ffmpeg_bin),
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=duration={duration_sec}:size=320x240:rate=15",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=1000:duration={duration_sec}",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(path),
        ]
        subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
        )
        return path

    return _create