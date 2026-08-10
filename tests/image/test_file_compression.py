import logging
from pathlib import Path
from src.image.compression.file_compression import file_compressor

# Silencia logs informativos no terminal para não poluir o output
logging.basicConfig(level=logging.WARNING)

TEST_INPUT: Path = Path("/home/bhzinn/FallByte/Teste/Translucenty/gato_translucenty")
TEST_OUTPUT_DIR: Path = Path("/home/bhzinn/FallByte/Teste/OUT/Compression")
QUALITY_LEVEL: int = 75


def test_file_compression_manual():
    if not TEST_INPUT.exists():
        print(f"Test skipped: Input file '{TEST_INPUT}' not found.")
        return

    TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = TEST_OUTPUT_DIR / f"{TEST_INPUT.stem}_compressed{TEST_INPUT.suffix}"

    print("\n" + "=" * 60)
    print("SINGLE FILE COMPRESSION TEST")
    print("=" * 60)

    orig_kb = TEST_INPUT.stat().st_size / 1024
    print(f"• Input File:   {TEST_INPUT.name} ({orig_kb:.2f} KB)")
    print(f"• Target Quality: {QUALITY_LEVEL}%")

    success = file_compressor(TEST_INPUT, output_path, quality=QUALITY_LEVEL)

    if success and output_path.exists():
        new_kb = output_path.stat().st_size / 1024
        reduction = ((orig_kb - new_kb) / orig_kb) * 100
        print("-" * 60)
        print(f"• Output File:  {output_path.name} ({new_kb:.2f} KB)")
        print(f"• Result:       {reduction:+.1f}% size reduction")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    test_file_compression_manual()