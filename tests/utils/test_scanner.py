import logging
from pathlib import Path
from src.utils.scanner import scan_image_files

# ==============================================================================
# CONSTRUCTOR / TEST CONFIGURATION
# Adjust this path to point to a local directory with images.
# ==============================================================================
TEST_SCAN_DIR: Path = Path("/home/bhzinn/FallByte/Teste/ImagePath")
RECURSIVE_SCAN: bool = True

logging.basicConfig(level=logging.INFO)


def test_scanner_manual():
    """
    Manual test for scan_image_files utility.
    Prints all discovered image paths found in target directory.
    """
    if not TEST_SCAN_DIR.exists():
        print(f"Test skipped: Directory '{TEST_SCAN_DIR}' does not exist.")
        return

    print(f"\nScanning directory: '{TEST_SCAN_DIR}'...")
    found_files = scan_image_files(TEST_SCAN_DIR, recursive=RECURSIVE_SCAN)

    print(f"\nTotal images found: {len(found_files)}")
    for file_path in found_files:
        print(f"  • {file_path.name} ({file_path.suffix})")


if __name__ == "__main__":
    test_scanner_manual()