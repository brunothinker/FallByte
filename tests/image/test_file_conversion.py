import logging
from pathlib import Path
from typing import List
from src.image.conversion.file_conversion import file_converter

# ==============================================================================
# CONSTRUCTOR / TEST CONFIGURATION
# Adjust these paths and formats to control the multi-format test suite.
# ==============================================================================
TEST_INPUT_FILE: Path = Path("/home/bhzinn/FallByte/Teste/Translucenty/gato_translucenty")
TEST_OUTPUT_DIR: Path = Path("/home/bhzinn/FallByte/Teste/OUT/Translucenty")

# All supported output formats available in FallByte
TARGET_FORMATS_TO_TEST: List[str] = [
    "JPEG", "PNG", "WEBP", "BMP", "TIFF", "GIF", "ICO", "PPM", "PDF"
]
DEFAULT_TRANSPARENCY_COLOR: str = "#FFFFFF"  # White background fallback

logging.basicConfig(level=logging.INFO)


def test_file_conversion_manual():
    """
    Manual integration test for file_converter.
    Iterates through all supported target formats and attempts to convert the source image.
    """
    if not TEST_INPUT_FILE.exists():
        print(f"Test skipped: Input file '{TEST_INPUT_FILE}' does not exist.")
        return

    print(f"\nStarting multi-format file conversion test for '{TEST_INPUT_FILE.name}'...")
    print(f"Formats to test: {', '.join(TARGET_FORMATS_TO_TEST)}\n" + "-" * 50)

    summary = {"success": 0, "failed": 0}

    for fmt in TARGET_FORMATS_TO_TEST:
        # Determine appropriate file extension
        ext = "jpg" if fmt.upper() in ("JPEG", "JPG") else fmt.lower()
        output_file = TEST_OUTPUT_DIR / f"{TEST_INPUT_FILE.stem}_converted.{ext}"

        print(f"\nTesting conversion to: [{fmt}]")

        success = file_converter(
            input_path=TEST_INPUT_FILE,
            output_path=output_file,
            target_format=fmt,
            transparency_replacement_color=DEFAULT_TRANSPARENCY_COLOR
        )

        if success:
            summary["success"] += 1
            print(f"✅ [{fmt}] Saved successfully -> {output_file.name}")
        else:
            summary["failed"] += 1
            print(f"❌ [{fmt}] Conversion failed!")

    print("\n" + "=" * 50)
    print(f"📊 Multi-Format Test Summary:")
    print(f"• Total Tested: {len(TARGET_FORMATS_TO_TEST)}")
    print(f"• Passed:       {summary['success']}")
    print(f"• Failed:       {summary['failed']}")
    print("=" * 50)


if __name__ == "__main__":
    test_file_conversion_manual()