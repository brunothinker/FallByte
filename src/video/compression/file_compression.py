import logging
import subprocess
from pathlib import Path

from src.video.utils.binary_manager import get_ffmpeg_path

# Setup module logger
logger = logging.getLogger(__name__)


def file_compressor(
    input_path: Path, output_path: Path, quality: int = 80
) -> bool:
    """Compresses a single video file while strictly maintaining its ORIGINAL format.

    Maps the percentage quality scale (1-100) to FFmpeg's Constant Rate Factor
    (CRF).

    Args:
        input_path (Path): Path to the source video file.
        output_path (Path): Path where the compressed video will be saved.
        quality (int, optional): Quality level percentage (1-100). Higher is
          better quality. Defaults to 80.

    Returns:
        bool: True if compression succeeded, False otherwise.
    """
    try:
        # Clamp quality range between 1 and 100
        quality = max(1, min(100, quality))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Retrieve absolute FFmpeg path for current OS
        ffmpeg_bin = get_ffmpeg_path()

        # Map 1-100 quality scale to x264 CRF scale (18 = visually lossless, 40 = low quality)
        # Quality 100 -> CRF 18 | Quality 80 -> CRF 22 | Quality 50 -> CRF 29
        crf = round(18 + (100 - quality) * 0.22)

        # Build FFmpeg compression command:
        # -y: Overwrite output file
        # -c:v libx264: Industry standard video codec
        # -crf: Rate control factor based on user quality setting
        # -preset medium: Balanced speed/compression ratio
        # -c:a aac: Standard audio codec
        cmd = [
            str(ffmpeg_bin),
            "-y",
            "-i",
            str(input_path),
            "-c:v",
            "libx264",
            "-crf",
            str(crf),
            "-preset",
            "medium",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(output_path),
        ]

        # Execute FFmpeg process suppressing stdout/stderr output to logs
        subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )

        logger.info(
            f"Successfully compressed '{input_path.name}' "
            f"[Format: {input_path.suffix.upper()} | Quality: {quality}% | CRF: {crf}]."
        )
        return True

    except subprocess.CalledProcessError as e:
        logger.error(
            f"FFmpeg error compressing '{input_path.name}': {e.stderr.decode('utf-8', errors='ignore')}"
        )
        return False
    except Exception as e:
        logger.error(
            f"Failed to compress '{input_path.name}': {e}", exc_info=True
        )
        return False