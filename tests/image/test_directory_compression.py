import logging
from pathlib import Path
from src.image.compression.directory_compression import directory_compressor
from src.image.utils.analysis import UNCOMPRESSIBLE_FORMATS
from src.utils.progress import ProgressInfo

logging.basicConfig(level=logging.WARNING)

TEST_INPUT_DIR: Path = Path("/home/bhzinn/FallByte/Teste/OUT/Dir")
TEST_OUTPUT_DIR: Path = Path("/home/bhzinn/FallByte/Teste/OUT/DirectoryCompression")
QUALITY_LEVEL: int = 75


def print_file_log(info: ProgressInfo):
    """Prints a clean, color-coded per-file result in terminal with uncompressible flags."""
    filename = info.file_path.name if info.file_path else "Unknown"

    if not info.success:
        print(f"  [{info.current:02d}/{info.total:02d}] [FAIL] {filename:<26} | SKIPPED / FAILED")
        return

    ext = info.file_path.suffix.lstrip(".").upper() if info.file_path else ""
    is_uncompressible = ext in UNCOMPRESSIBLE_FORMATS

    orig_kb = info.orig_bytes / 1024
    comp_kb = info.comp_bytes / 1024

    reduction = 0.0
    if info.orig_bytes > 0:
        reduction = ((info.orig_bytes - info.comp_bytes) / info.orig_bytes) * 100

    orig_str = f"{orig_kb / 1024:.2f} MB" if orig_kb >= 1024 else f"{orig_kb:.1f} KB"
    comp_str = f"{comp_kb / 1024:.2f} MB" if comp_kb >= 1024 else f"{comp_kb:.1f} KB"

    if is_uncompressible:
        tag = "[INFO]"
        status_note = f"| RAW / UNCOMPRESSIBLE ({ext})"
        print(
            f"  [{info.current:02d}/{info.total:02d}] {tag} {filename:<26} "
            f"| {orig_str:>8} -> {comp_str:>8} {status_note}"
        )
    else:
        tag = "[OK]  "
        print(
            f"  [{info.current:02d}/{info.total:02d}] {tag} {filename:<26} "
            f"| {orig_str:>8} -> {comp_str:>8} | {reduction:>+6.1f}%"
        )


def test_directory_compression_manual():
    if not TEST_INPUT_DIR.exists():
        print(f"Test skipped: Input directory '{TEST_INPUT_DIR}' does not exist.")
        return

    print("\n" + "=" * 65)
    print("DIRECTORY COMPRESSION TEST")
    print("=" * 65)
    print(f"Input Directory:  {TEST_INPUT_DIR}")
    print(f"Output Directory: {TEST_OUTPUT_DIR}")
    print(f"Target Quality:   {QUALITY_LEVEL}%\n" + "-" * 65)

    stats = directory_compressor(
        input_dir=TEST_INPUT_DIR,
        output_dir=TEST_OUTPUT_DIR,
        quality=QUALITY_LEVEL,
        progress_callback=print_file_log
    )

    print("-" * 65)
    print("COMPRESSION SUMMARY")
    print("=" * 65)
    orig_mb = stats["original_bytes"] / (1024 * 1024)
    comp_mb = stats["compressed_bytes"] / (1024 * 1024)
    reduction_pct = 0.0
    if stats["original_bytes"] > 0:
        reduction_pct = ((stats["original_bytes"] - stats["compressed_bytes"]) / stats["original_bytes"]) * 100

    print(f"Successful:       {stats.get('success')}")
    print(f"Failed:           {stats.get('failed')}")
    print(f"Time Elapsed:     {stats.get('elapsed_seconds')}s")
    print(f"Original Size:    {orig_mb:.2f} MB")
    print(f"Compressed Size:  {comp_mb:.2f} MB")
    print(f"Total Reduction:  {reduction_pct:+.1f}%")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    test_directory_compression_manual()