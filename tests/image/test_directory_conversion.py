import logging
from pathlib import Path
from typing import List
from src.image.conversion.directory_conversion import directory_converter
from src.image.utils.image_progress import ProgressInfo

# ==============================================================================
# CONSTRUCTOR / TEST CONFIGURATION
# Adjust these paths and formats to control the multi-format directory test suite.
# ==============================================================================
TEST_INPUT_DIR: Path = Path("/home/bhzinn/FallByte/Teste/ImagePath")
TEST_OUTPUT_BASE_DIR: Path = Path("/home/bhzinn/FallByte/Teste/OUT/Dir")

# List of target formats to test in batch execution
TARGET_FORMATS_TO_TEST: List[str] = [
    "JPEG", "PNG", "WEBP", "BMP", "TIFF", "GIF", "ICO", "PPM", "PDF"
]
DEFAULT_TRANSPARENCY_COLOR: str = "#FFFFFF"

logging.basicConfig(level=logging.INFO)


def on_progress_update(info: ProgressInfo):
    """Callback function to print progress details to terminal."""
    print(
        f"  └─ [{info.current}/{info.total}] {info.percentage}% "
        f"| Elapsed: {info.elapsed_seconds}s "
        f"| ETA: {info.estimated_remaining_seconds}s"
    )


def test_directory_conversion_manual():
    """
    Manual integration test for directory_converter.
    Converts an entire folder of images across all supported target formats,
    tracking real-time progress for each run.
    """
    if not TEST_INPUT_DIR.exists():
        print(f"Test skipped: Input directory '{TEST_INPUT_DIR}' does not exist.")
        return

    print(f"\nStarting multi-format DIRECTORY conversion test...")
    print(f"Input Directory: {TEST_INPUT_DIR}")
    print(f"Formats to test: {', '.join(TARGET_FORMATS_TO_TEST)}\n" + "=" * 60)

    overall_stats = {}

    for fmt in TARGET_FORMATS_TO_TEST:
        # Output folder per format to keep files organized (e.g., .../OUT/Dir/WEBP)
        format_output_dir = TEST_OUTPUT_BASE_DIR / fmt.upper()

        print(f"\n🔄 [BATCH RUN] Converting directory to format: [{fmt}]")
        print(f"Output Directory: {format_output_dir}")
        print("-" * 50)

        stats = directory_converter(
            input_dir=TEST_INPUT_DIR,
            output_dir=format_output_dir,
            target_format=fmt,
            transparency_replacement_color=DEFAULT_TRANSPARENCY_COLOR,
            progress_callback=on_progress_update
        )

        overall_stats[fmt] = stats

    # ==========================================================================
    # FINAL MULTI-FORMAT BATCH SUMMARY
    # ==========================================================================
    print("\n" + "=" * 60)
    print("📊 MULTI-FORMAT DIRECTORY CONVERSION SUMMARY")
    print("=" * 60)

    for fmt, stat in overall_stats.items():
        success = stat.get("success", 0)
        failed = stat.get("failed", 0)
        elapsed = stat.get("elapsed_seconds", 0)
        status_icon = "✅" if failed == 0 else "⚠️"

        print(
            f"{status_icon} [{fmt.ljust(5)}] -> "
            f"Success: {str(success).rjust(2)} | "
            f"Failed: {str(failed).rjust(2)} | "
            f"Time: {elapsed}s"
        )

    print("=" * 60)


if __name__ == "__main__":
    test_directory_conversion_manual()