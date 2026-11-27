"""Lossless JPEG metadata stripping at the bitstream marker level."""

from __future__ import annotations

import struct

# JPEG marker constants (ITU-T T.81)
_SOI = b"\xff\xd8"
_EOI = 0xD9
_SOS = 0xDA
_RST_FIRST = 0xD0
_RST_LAST = 0xD7
_TEM = 0x01

# Standalone markers without a 2-byte length payload
_STANDALONE_MARKERS = frozenset({0x00, _TEM, 0xD8, _EOI, *range(_RST_FIRST, _RST_LAST + 1)})

# Application markers essential for decoding color space / pixel interpretation:
# - 0xE0 (APP0): JFIF header (aspect ratio / thumbnail stripped if separate, standard header)
# - 0xEE (APP14): Adobe color transform tag (prevents CMYK/YCCK color inversion)
_PRESERVED_APP_MARKERS = frozenset({0xE0, 0xEE})

# Metadata markers stripped losslessly without touching DCT coefficients:
# - 0xE1 (APP1): EXIF, GPS, XMP
# - 0xE2..0xED, 0xEF (APP2..APP13, APP15): ICC profile, FlashPix, IPTC/Photoshop IRB, etc.
# - 0xFE (COM): JPEG comment blocks
_STRIPPED_MARKERS = frozenset(
    {marker for marker in range(0xE1, 0xF0) if marker not in _PRESERVED_APP_MARKERS}
    | {0xFE}
)


def strip_jpeg_metadata_bytes(data: bytes) -> bytes:
    """Strips EXIF, XMP, GPS, ICC, IPTC, and COM segments from a JPEG bitstream losslessly.

    Preserves all quantization tables (DQT), Huffman tables (DHT), frame headers (SOF),
    restart intervals (DRI), Adobe color transform markers (APP14), JFIF headers (APP0),
    and the compressed entropy-coded scan data untouched, avoiding generational DCT loss.

    Args:
        data: Raw bytes of a valid JPEG file.

    Returns:
        Sanitized JPEG bytes with identical DCT coefficients and zero metadata markers.

    Raises:
        ValueError: If the byte stream is not a valid or complete JPEG file.
    """
    if len(data) < 4 or not data.startswith(_SOI):
        raise ValueError("Input is not a valid JPEG bitstream (missing SOI marker).")

    out = bytearray(_SOI)
    pos = 2
    length = len(data)
    saw_sos = False
    saw_eoi = False

    while pos < length:
        if data[pos] != 0xFF:
            raise ValueError(f"Malformed JPEG marker alignment at byte offset {pos}.")

        # Skip any 0xFF fill padding bytes before the marker code
        while pos < length and data[pos] == 0xFF:
            pos += 1

        if pos >= length:
            raise ValueError("Truncated JPEG marker at end of stream.")

        marker = data[pos]
        pos += 1

        if marker == _EOI:
            out.extend((0xFF, _EOI))
            saw_eoi = True
            break

        if marker in _STANDALONE_MARKERS:
            out.extend((0xFF, marker))
            continue

        if pos + 2 > length:
            raise ValueError(f"Truncated length field for JPEG marker 0xFF{marker:02X}.")

        seg_len = struct.unpack(">H", data[pos : pos + 2])[0]
        if seg_len < 2 or pos + seg_len > length:
            raise ValueError(
                f"Invalid segment length ({seg_len}) for JPEG marker 0xFF{marker:02X}."
            )

        seg_end = pos + seg_len
        if marker not in _STRIPPED_MARKERS:
            out.extend((0xFF, marker))
            out.extend(data[pos:seg_end])

        pos = seg_end

        if marker == _SOS:
            saw_sos = True
            # Entropy-coded scan data runs until an unescaped marker (0xFF followed by
            # a non-zero byte that is not a restart marker RST0..RST7).
            scan_start = pos
            while pos < length:
                if data[pos] != 0xFF:
                    pos += 1
                    continue

                if pos + 1 >= length:
                    raise ValueError("Truncated entropy-coded scan data in JPEG.")

                next_byte = data[pos + 1]
                if next_byte == 0x00 or _RST_FIRST <= next_byte <= _RST_LAST:
                    pos += 2
                    continue

                # Reached the next marker boundary (e.g., EOI or another SOS in progressive JPEG)
                break

            out.extend(data[scan_start:pos])

    if not saw_sos or not saw_eoi:
        raise ValueError("Incomplete JPEG bitstream (missing SOS or EOI marker).")

    return bytes(out)
