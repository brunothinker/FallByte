# Audio Module — Technical Documentation

> **Status:** v1 implementation complete and integrated (Engine, UI, Locales, and Test Suite — **472 passing tests**).
>
> **Architectural Isolation:** 100% independent from `src/video/` and `src/image/`, enforced by a static AST test (`test_audio_module_has_zero_cross_imports_from_video_or_image`).

## 1. Overview and Directory Structure

The audio module operates as an autonomous domain within the ecosystem, following the same batch, progress, and atomic write contracts as the video and image modules without any cross-domain code coupling.

```
src/audio/
├── __init__.py
├── engine/
│   ├── __init__.py
│   ├── file_compressor.py      # Compression with quality -> bitrate mapping and stereo fallback
│   └── file_converter.py       # Format conversion with cover-art stripping and stereo fallback
└── utils/
    ├── __init__.py
    ├── audio_scanner.py        # Dedicated audio file and directory scanner
    ├── binary_manager.py       # Bundled FFmpeg binary path resolution (parents[3])
    └── ffmpeg_audio_utils.py   # Stream probing, codecs, bitrates, and FFmpeg strategy runner

ui/
├── controllers/
│   ├── audio_compression_controller.py
│   └── audio_conversion_controller.py
└── pages/
    ├── audio_compression_page.py
    └── audio_conversion_page.py

tests/engine/
└── test_audio_engine.py        # Unit tests, FFmpeg integration, edge cases, and AST validation
```

## 2. Supported Formats and Business Rules

### 2.1 Recognized Extensions (`SUPPORTED_AUDIO_EXTENSIONS`)

* **Lossy:** `.mp3`, `.m4a`, `.aac`, `.ogg`, `.opus`, `.wma`
* **Lossless / PCM:** `.flac`, `.wav`, `.aiff`

### 2.2 Compression (`file_compressor.py`)

* **Quality** $\rightarrow$ **Bitrate Mapping (`quality_to_bitrate_kbps`):**
  * Linear scaling between codec-specific minimum and maximum bounds defined in `BITRATE_RANGES_KBPS`:
    * `mp3` (`libmp3lame`): `48` – `320` kbps
    * `m4a` (`aac`): `64` – `320` kbps
    * `aac` (`aac` / `-f adts`): `64` – `320` kbps
    * `ogg` (`libvorbis`): `48` – `320` kbps (automatically capped at `256` kbps when probing detects `channels == 1`, preventing Vorbis encoder initialization failures)
    * `opus` (`libopus`): `32` – `192` kbps
* **Uncompressible Formats (`UNCOMPRESSIBLE_AUDIO_FORMATS`):**
  * Contains `{"FLAC", "WAV", "WMA", "AIFF"}`.
  * Files with these extensions are atomically copied (`copy_original_file_atomically`) without re-encoding.
  * *Technical note:* `FLAC`, `WAV`, and `AIFF` are lossless; `WMA` is a lossy format, but remains in this list in v1 due to the lack of a dedicated WMA encoder in the bundled FFmpeg build.

### 2.3 Conversion (`file_converter.py`)

* **Output Targets (`AUDIO_CONVERSION_TARGETS`):** `mp3`, `wav`, `flac`, `aac`, `ogg`, `m4a`, `opus`.
* **Same-Extension Bypass:**
  * If `input_ext == target_fmt`, the file is atomically copied without invoking FFmpeg.
  * *Technical note:* Same-extension conversion does not perform sample rate, bit depth, or channel normalization (e.g., `.wav` $\rightarrow$ `wav` preserves the original file intact).
* **Embedded Cover-Art Stripping:**
  * All encoding commands use `-map 0:a:0 -vn -sn -dn` to prevent embedded cover art (`mjpeg`/`png` in `.mp3`, `.m4a`, or `.flac`) from being interpreted as video tracks or causing muxing errors in audio-only output containers.

## 3. Resilience and FFmpeg Strategies

Both compression and conversion rely on a two-stage fallback pipeline (`run_audio_strategies`):

1. **`standard` strategy:** Executes encoding while preserving the original channel count (`-map 0:a:0 -vn -sn -dn`).
2. **`rescue` strategy:** Triggered automatically if the standard strategy fails. Adds tolerance for corrupted headers/timestamps (`-fflags +genpts -err_detect ignore_err`) and forces stereo downmixing (`-ac 2`), resolving rejections from encoders such as `libmp3lame` or `libvorbis` when processing multichannel sources (5.1 / 7.1).

## 4. Implementation Notes and Tracked Technical Debt

Known v1 behaviors intentionally preserved to maintain initial domain isolation:

1. **Dual Active Process Registries (`atexit`):**
   * `../src/audio/utils/audio_ffmpeg_utils.py` and `../src/video/utils/video_ffmpeg_utils.py` maintain separate `_active_processes` registries and `atexit` hooks (verified via `test_terminate_active_processes_kills_orphans_and_removes_partials`). Any explicit UI shutdown routine (e.g., main window `closeEvent`) must terminate both until unified.
2. **Directory Depth Sensitivity in `binary_manager.py`:**
   * Bundled binary resolution relies on `Path(__file__).resolve().parents[3]`. Moving the module requires updating the `parents` index.
3. **Stream Probing Regex (`_AUDIO_STREAM_RE`) — Resolved:**
   * Sample rate capture (`(?:,\s*(\d+)\s*Hz)?`) is optional during probing (`sample_rate = 0` when omitted), allowing legacy/exotic WMA and AIFF streams to be processed without being rejected for lacking an explicit sample rate.
4. **Single-File Cancellation Cleanup:**
   * `AudioConversionController._execute_single_file` removes the destination file directly upon cancellation, whereas `AudioCompressionController` checks `pre_existed` before deletion.

---

## 5. Prioritized Evolution Checklist

### Phase 1 — Functional Requirements (Priority 1: Core Functionality & Format Support)
Focused on ensuring all conversion and compression workflows operate end-to-end across all supported formats without parsing failures:

- [x] **`.aac` (ADTS) compression support:** Removed `aac` from `UNCOMPRESSIBLE_AUDIO_FORMATS`, added it to `BITRATE_RANGES_KBPS` (`64`–`320` kbps), and configured `-f adts` in `get_audio_codec_args` for real re-encoding.
- [x] **Stream parser resilience (`_AUDIO_STREAM_RE`):** Made sample rate capture optional during probing to accept legacy/exotic streams (e.g., WMA/AIFF) without failing as "no audio stream".
- [x] **Full format matrix validation in the test suite:** Covered conversion/compression across all supported formats (`.mp3`, `.m4a`, `.aac`, `.ogg`, `.opus`, `.flac`, `.wav`, `.aiff`, plus `.wma` atomic bypass) with per-encoder `pytest.mark.skipif` guards (`libmp3lame`, `libvorbis`, `libopus`), progress callback assertions, and active process cleanup validation.
- [x] **Per-codec bitrate curves (functional refinement):** Tuned quality floors for specific codecs (e.g., `64` kbps minimum floor for stereo `aac`/`m4a` and `256` kbps cap for mono `ogg`/`libvorbis`).

### Phase 2 — Non-Functional Requirements (Priority 2: Hardening, Bug Fixes & Unification)
Focused on operational resilience, preventing orphan processes, and reducing structural duplication:

- [ ] **Unified active process termination:** Provide a single shutdown entry point on application exit to prevent orphaned audio FFmpeg processes.
- [ ] **Consistent single-file cancellation cleanup:** Add a `pre_existed` guard to `AudioConversionController._execute_single_file` mirroring `AudioCompressionController`.
- [ ] **`binary_manager.py` unification:** Centralize bundled binary path resolution (eliminating fragile `parents[3]` coupling duplicated across modules).
- [ ] **`ffmpeg_core.py` unification (Final stage):** Extract shared neutral infrastructure between `ffmpeg_utils.py` (video) and `ffmpeg_audio_utils.py` (audio)—`base_command`, `-progress pipe:1` parser, `_active_processes`, `_terminate_process`, and generic strategy runner—while keeping codec and stream rules isolated per domain.