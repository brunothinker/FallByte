"""Shared pytest fixtures for the FallByte test suite.

Provides a mocked Flet page, isolated input/output workspaces and factories
that generate synthetic images (Pillow) and videos (bundled FFmpeg).
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Must run BEFORE any `src` / `ui` import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import flet as ft

# Pre-register HEIF opener to handle HEIC images in fixtures/tests
import pillow_heif

pillow_heif.register_heif_opener()

import pytest
from PIL import Image

from src.video.utils.binary_manager import get_ffmpeg_path


class DummyControl(ft.Control):
    """Dummy control to satisfy component initialization in tests."""


@pytest.fixture
def mock_page() -> MagicMock:
    """Provides a mocked ft.Page instance for headless UI testing.

    Returns:
        MagicMock: Page double exposing `route`, `overlay` and `dialog`.
    """
    page = MagicMock()
    page.route = "/"
    page.overlay = []
    page.dialog = None
    return page


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Creates temporary isolated directories for input and output test files.

    Args:
        tmp_path (Path): Pytest-provided unique temporary directory.

    Returns:
        tuple[Path, Path]: The (input_dir, output_dir) pair, both existing.
    """
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    return input_dir, output_dir


@pytest.fixture
def create_sample_image():
    """Factory fixture to generate sample images with customizable mode and size.

    Returns:
        Callable[..., Path]: Function `(path, mode, size, fmt) -> Path` that
            writes a solid-color image and returns its path.
    """

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
    """Factory fixture to generate sample synthetic videos using FFmpeg lavfi.

    Returns:
        Callable[..., Path]: Function `(path, duration_sec, codec, crf, size,
            noisy) -> Path` that encodes a test pattern with a sine tone.
            Defaults to a small H.264 + AAC clip. Pass `codec="libx265"` for a
            HEVC source and `noisy=True` for a phone-like source (yuv420p with
            film grain, so the video stream dominates the file size).
    """

    def _create(
        path: Path,
        duration_sec: int = 1,
        codec: str = "libx264",
        crf: int | None = None,
        size: str = "320x240",
        noisy: bool = False,
    ) -> Path:
        ffmpeg_bin = get_ffmpeg_path()
        cmd = [
            str(ffmpeg_bin),
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=duration={duration_sec}:size={size}:rate=15",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=1000:duration={duration_sec}",
            *(
                ["-vf", "noise=alls=25:allf=t+u,format=yuv420p"]
                if noisy
                else []
            ),
            "-c:v",
            codec,
            *(["-crf", str(crf)] if crf is not None else []),
            *(
                ["-tag:v", "hvc1"]
                if codec == "libx265" and path.suffix in (".mp4", ".mov")
                else []
            ),
            "-c:a",
            "aac",
            str(path),
        ]
        subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
        )
        return path

    return _create