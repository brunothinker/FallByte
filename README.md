# FallByte

> Drop the weight. Keep the quality.

FallByte is a fast, lightweight, and local-first media optimization suite for **images, videos, and audio**, designed to reclaim disk space without compromising quality or privacy.

---

## About the Project

Most media optimization tools require uploading sensitive files to cloud servers or dealing with ad-heavy web interfaces. **FallByte** runs 100% locally on your machine, processing media offline with speed, safety, and precision.

---

## Key Features

- **Local-First & Private:** Your files never leave your system. No server uploads, no telemetry, no internet required.
- **Embedded Media Engine (FFmpeg):** Video and audio processing powered by a bundled static FFmpeg binary, so no external installation is required.
- **Single file or whole folder:** Tools work on a single file or recursively across folders, preserving the original directory structure in the output.
- **Safe by design:** Existing files are never overwritten (outputs get a unique name or a new session folder), writes are atomic, and cancelling a batch cleans up only what that session created.
- **Themes & languages:** 5 dark and 5 light themes, with 10 supported interface languages (auto-detected from your system).

### Images

- **Compression:** Quality control, PNG palette quantization, and optional metadata stripping *(EXIF, GPS, XMP, ICC)* while strictly keeping the original format *(JPEG, PNG, WEBP, TIFF)*[cite: 20]. Formats that cannot be safely re-encoded (BMP, PPM, GIF, ICO, HEIC/HEIF) and animated PNGs are copied untouched[cite: 20]. If the result is not smaller (and metadata stripping is not enabled), the original is kept[cite: 20].
- **Conversion:** Read `JPEG`, `PNG`, `WEBP`, `BMP`, `TIFF`, `GIF`, `PPM`, `ICO`, `HEIC`, and `HEIF`, and convert to `JPEG`, `PNG`, `WEBP`, `BMP`, `TIFF`, `GIF`, `ICO`, `PPM`, or `PDF`[cite: 20]. Transparency is blended into a background color of your choice for formats without alpha[cite: 20]. EXIF rotation, ICC profiles, animations, and multi-page TIFF are handled when the target allows it[cite: 20].
- **Resizing & Scaling:** Resize single images or entire folders (`JPEG`, `PNG`, `WEBP`, `BMP`, `TIFF`, `GIF`, `PPM`, `ICO`, `HEIC`, `HEIF`) using Lanczos resampling either by **maximum target dimensions** *(bounding box with aspect ratio preserved)* or by **percentage scale** (`1%–100%`), with an optional safeguard to prevent upscaling smaller images and automatic EXIF orientation handling.
- **Metadata Removal:** Strip sensitive **EXIF, GPS coordinates, XMP, ICC profiles, PNG textual chunks (`tEXt`/`iTXt`), and GIF comments** across single files or batch directories while baking EXIF orientation into pixel data and preserving animation frames (`HEIC`/`HEIF` sources are exported as clean `PNG` files).

### Videos

- **Conversion:** From `MP4`, `MKV`, `WEBM`, `MOV`, `AVI`, `WMV`, `M4V`, `FLV`, `TS`, `3GP`, and `MPG` into `MP4`, `MKV`, `WEBM`, `MOV`, `AVI`, or `WMV`[cite: 20]. FFmpeg strategies go from lossless remux, to partial re-encode, to full re-encode, to a "rescue" mode for damaged files[cite: 20].
- **Compression:** Quality scale mapped to CRF/qscale, keeping the original container[cite: 20]. HEVC sources stay HEVC[cite: 20].
- **HEVC 10-bit / HDR:** When conversion to MP4, MOV or MKV requires re-encoding a 10-bit HEVC source, FallByte uses `libx265` to keep 10-bit video (`yuv420p10le`), with 8-bit H.264 as a fallback[cite: 20]. MP4 and MOV use the `hvc1` tag for HEVC playback compatibility[cite: 20].

### Audio

- **Conversion:** From `MP3`, `M4A`, `AAC`, `OGG`, `OPUS`, `FLAC`, `WAV`, `WMA`, and `AIFF` into `MP3`, `M4A`, `OPUS`, `OGG`, `FLAC`, or `WAV`[cite: 20]. Embedded cover art is stripped and only the main audio track is converted[cite: 20].
- **Compression:** Quality scale mapped to bitrate for lossy formats (`MP3`, `M4A`, `AAC`, `OGG`, `OPUS`)[cite: 20]. Lossless or legacy formats (`FLAC`, `WAV`, `WMA`, `AIFF`) are copied untouched, and the original is kept if re-encoding would not make the file smaller[cite: 20].
- **Video-to-Audio Extraction:** Extract audio tracks from video files (`MP4`, `MKV`, `WEBM`, `MOV`, `AVI`, `WMV`, `M4V`, `FLV`, `TS`, `3GP`, `MPG`) directly into `MP3`, `M4A`, `OPUS`, `OGG`, `FLAC`, or `WAV` for a single video or an entire folder, safely skipping silent video files[cite: 20].
- **Volume Normalization (EBU R128):** Batch-normalize perceived loudness across folders of audio files (`MP3`, `M4A`, `AAC`, `OGG`, `OPUS`, `FLAC`, `WAV`) using FFmpeg's `loudnorm` filter with target presets for **Music / Streaming (`-14 LUFS`)**, **Podcast / Voice (`-16 LUFS`)**, and **Broadcast / Standard (`-23 LUFS`)**, preserving original formats and sample rates[cite: 20].

---

## OS Support & Download

| Operating System | Package | Status |
|---|---|---|
| Linux (Ubuntu / Debian / Mint) | Native `.deb` | Supported |
| Linux (Fedora / RHEL / openSUSE) | Native `.rpm` | Supported |
| Linux (Arch / Universal Linux) | Portable `.AppImage` | Supported |
| Windows (x64) | Portable `.zip` | Supported |

> **[Get FallByte for your OS (Official Download Page)](https://brunothinker.github.io/page/)**
>
> *Prefer raw build artifacts? Browse all compiled files on the [GitHub Releases Page](https://github.com/brunothinker/FallByte/releases).*

You can verify an installation with:

```bash
fallbyte --version
fallbyte --smoke-test   # checks dependencies, bundled FFmpeg and image encoders
```

---

## Development

```bash
git clone https://github.com/brunothinker/FallByte.git
cd FallByte
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

To run the tests:

```bash
pip install -r tests/requirements-dev.txt
pytest
```

Logs are written to `~/.config/fallbyte/fallbyte.log` on Linux and `%APPDATA%\FallByte\fallbyte.log` on Windows (run with `--debug` for verbose output)[cite: 20].

Want to contribute? Read [CONTRIBUTING.md](docs/CONTRIBUTING.md) and [ARCHITECTURE.md](docs/ARCHITECTURE.md) first[cite: 20].

---

## Stack

- **Language:** Python
- **UI Framework:** Flet (Flutter for Python)
- **Image Processing:** Pillow, pillow-heif
- **Media Engine:** FFmpeg (static binaries, video and audio)
- **Localization:** YAML locale files

---

## Security

Found a vulnerability? Please follow [SECURITY.md](SECURITY.md) instead of opening a public issue[cite: 20].

## License & Third-Party Notices

FallByte is licensed under the **[GNU General Public License v3.0](https://github.com/brunothinker/FallByte/blob/main/LICENSE)** (GPLv3)[cite: 20].

This project bundles third-party binaries (such as FFmpeg static builds) and depends on open-source libraries (Flet, Pillow, pillow-heif, PyYAML)[cite: 20]. For licensing terms, source locations, and binary build configurations, see [THIRD_PARTY_NOTICES.md](https://github.com/brunothinker/FallByte/blob/main/docs/THIRD_PARTY_NOTICES.md)[cite: 20].
