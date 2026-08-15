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
    quality. Target format container requirements are checked to select
    compatible audio/video codecs automatically.

    Args:
        input_path (Path): Path to the source video file.
        output_path (Path): Path where the converted video will be saved.
        target_format (str): Desired output extension/format (e.g., 'mp4',
          'mkv', 'webm', 'mov', 'avi', 'wmv').

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

        # Select compatible audio and video codecs based on target container
        if target_fmt == "webm":
            codec_args = ["-c:v", "libvpx-vp9", "-row-mt", "1", "-cpu-used", "4", "-c:a", "libopus"]
        elif target_fmt == "wmv":
            codec_args = ["-f", "asf", "-c:v", "wmv1", "-c:a", "wmav2"]
        else:
            # Universal default codecs for MP4, MKV, MOV, AVI
            codec_args = ["-c:v", "libx264", "-c:a", "aac"]

        # Build FFmpeg conversion command:
        # -y: Overwrite output file without asking
        # -i: Input file path
        cmd = [
            str(ffmpeg_bin),
            "-y",
            "-i",
            str(input_path),
            *codec_args,
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