# Tests layout

    tests/
    ├── conftest.py                                   shared fixtures (mock page, workspaces, sample media)
    ├── test_main.py                                  app entrypoint, routing, session navigation guard
    ├── audio/                                        src/audio/ (no UI)
    │   ├── conftest.py                               shared audio fixtures (FFmpeg check, synthetic WAV/MP3)
    │   ├── helpers.py                                audio stream & bitrate inspection helpers
    │   ├── test_audio_architecture_and_scanner.py    module structure, format registries, directory scanner
    │   ├── test_audio_batch.py                       batch directory audio conversion and compression
    │   ├── test_audio_compression.py                 lossy bitrate reduction, metadata & artwork preservation
    │   ├── test_audio_conversion.py                  format matrix, codec defaults, container flags
    │   └── test_audio_ffmpeg_utils.py                FFprobe parsing, stream mapping, bitrate scaling
    ├── batch/                                        src/utils/ batch sessions & file safety
    │   ├── test_batch_cleanup.py                     cancelled job rollback, empty folder pruning
    │   ├── test_batch_naming.py                      unique filename suffixing on destination collisions
    │   ├── test_output_directory.py                  session folder creation, nested/same-dir validation
    │   └── test_run_batch.py                         generic batch runner orchestration, progress & errors
    ├── image/                                        src/image/ (no UI)
    │   ├── test_image_compression.py                 lossy/lossless optimization, fallback behavior
    │   ├── test_image_conversion.py                  format matrix, transparency flattening, ICO clamp
    │   ├── test_image_metadata.py                    EXIF/metadata stripping and preservation
    │   ├── test_image_resize.py                      single-file resize: dimensions, percentage, EXIF, GIF, HEIC
    │   └── test_image_resize_directory.py            directory resize: hierarchy, HEIC remap, cancellation
    ├── ui/                                           ui/
    │   ├── conftest.py                               parametrized controller context & engine fakes
    │   ├── helpers.py                                shared UI state assertion helpers
    │   ├── test_controller_execution.py              single-file & batch execution flows across controllers
    │   ├── test_controller_integration.py            controllers + real engines, preflight & overwrite safety
    │   ├── test_controller_pickers.py                file/folder picker locks, callbacks, safe initial dirs
    │   ├── test_controller_validation_and_cancel.py  path validation, action routing, cancellation dialogs
    │   ├── test_dialogs_and_log_capture.py           summary/error dialogs, size formatting, log redirection
    │   ├── test_flet_controls.py                     headless mocked Flet page & basic control interactions
    │   ├── test_i18n.py                              YAML locale parity, placeholders, OS language detection
    │   └── test_ui_components_and_pages.py           theme colors, format lists, picker cards, pages & routes
    ├── utils/                                        src/utils/ infrastructure & diagnostics
    │   ├── test_binary_manager.py                    bundled FFmpeg/FFprobe binary resolution
    │   ├── test_config_manager.py                    JSON settings persistence, atomic writes, defaults
    │   └── test_smoke_check.py                       startup dependency & environment smoke checks
    └── video/                                        src/video/ (no UI)
        ├── test_video_cancellation.py                mid-encode process termination & partial file cleanup
        ├── test_video_compression.py                 CRF/preset encoding, size-growth guard, audio copy
        ├── test_video_conversion.py                  container/codec matrix, resolution & stream handling
        ├── test_video_ffmpeg_utils.py                FFprobe duration/codec detection, argument builders
        └── test_video_hevc.py                        H.265/HEVC encoding, Apple hvc1 tag, hardware fallback

Run all: `pytest`   |   engine only: `pytest tests/audio tests/batch tests/image tests/utils tests/video`   |   ui only: `pytest tests/ui`