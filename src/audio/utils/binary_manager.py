import logging
import os
import platform
from pathlib import Path

# Setup module logger
logger = logging.getLogger(__name__)


def get_ffmpeg_path() -> Path:
    """Resolves and returns the absolute path to the bundled FFmpeg binary.

    Selects the appropriate executable based on the host operating system
    (Linux or Windows) and ensures proper execution permissions on Unix systems.

    Returns:
        Path: Absolute path to the valid FFmpeg executable binary.

    Raises:
        OSError: If the operating system is unsupported.
        FileNotFoundError: If the FFmpeg binary is missing from the resources
          directory.
    """
    system = platform.system().lower()

    # Locate the resources/bin directory relative to the project root
    project_root = Path(__file__).resolve().parents[3]
    bin_dir = project_root / "resources" / "bin"

    if system == "linux":
        binary_path = bin_dir / "linux" / "ffmpeg"
    elif system == "windows":
        binary_path = bin_dir / "windows" / "ffmpeg.exe"
    else:
        logger.error(f"Unsupported operating system encountered: '{system}'")
        raise OSError(f"Unsupported operating system: {system}")

    # Check if binary file actually exists in resources
    if not binary_path.exists():
        logger.critical(
            f"FFmpeg binary not found at expected path: '{binary_path}'"
        )
        raise FileNotFoundError(
            f"FFmpeg binary not found for {system} at: '{binary_path}'"
        )

    # Ensure POSIX execution permissions (+x) on Linux
    if system != "windows" and not os.access(binary_path, os.X_OK):
        logger.info(
            f"Granting execution permissions to FFmpeg binary at '{binary_path}'"
        )
        binary_path.chmod(binary_path.stat().st_mode | 0o111)

    return binary_path