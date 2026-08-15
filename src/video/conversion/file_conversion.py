import logging
import shutil
import subprocess
from pathlib import Path

from src.video.utils.binary_manager import get_ffmpeg_path

# Setup module logger
logger = logging.getLogger(__name__)


def file_converter(
    input_path: Path,
    output_path: Path,
    target_format: str,
) -> bool:
    """Converts a video file to the specified target format using FFmpeg.

    If the input file is already in the target format, it bypasses re-encoding
    and copies the file directly to destination to save time and preserve
    quality.

    Args:
        input_path (Path): Path to the source video file.
        output_path (Path): Path where the converted video will be saved.
        target_format (str): Desired output extension/format (e.g., 'mp4',
          'mkv', 'webm', 'avi').

    Returns:
        bool: True if conversion succeeded, False otherwise.
    """
    try:
        # Ensure the destination directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        input_ext = input_path.suffix.lower().lstrip(".")
        target_fmt = target_format.lower().lstrip(".")

        # Bypass FFmpeg re-encoding if extensions match
        if input_ext == target_fmt:
            logger.info(
                f"Skipping re-encoding for '{input_path.name}': already .{target_fmt}. Copying file..."
            )
            shutil.copy2(input_path, output_path)
            return True

        # Retrieve absolute FFmpeg path for current OS
        ffmpeg_bin = get_ffmpeg_path()

        # Build FFmpeg conversion command:
        # -y: Overwrite output file without asking
        # -i: Input file path
        # -c:v libx264 / -c:a aac: Safe default codecs for universal container compatibility
        cmd = [
            str(ffmpeg_bin),
            "-y",
            "-i",
            str(input_path),
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(output_path),
        ]

        # Execute FFmpeg process suppressing stdout/stderr output to logs
        subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )

        logger.info(
            f"Successfully converted '{input_path.name}' to '{target_fmt}'."
        )
        return True

    except subprocess.CalledProcessError as e:
        logger.error(
            f"FFmpeg error converting '{input_path.name}': {e.stderr.decode('utf-8', errors='ignore')}"
        )
        return False
    except Exception as e:
        logger.error(
            f"Failed to convert '{input_path.name}': {e}", exc_info=True
        )
        return False