# Tests layout

    tests/
    ├── conftest.py                 shared fixtures (mock page, workspaces, sample media)
    ├── engine/                     src/ (no UI)
    │   ├── test_image_engine.py    image conversion matrix, ICO clamp, compression fallback
    │   ├── test_video_engine.py    FFmpeg conversion/compression, edge cases, cancellation
    │   └── test_batch_sessions.py  directory orchestrators, session folders, cleanup
    └── ui/                         ui/
        ├── test_controllers.py     4 controllers: characterization + engine integration
        └── test_components.py      mocked Flet controls, dialogs, format helpers

Run all: `pytest`   |   engine only: `pytest tests/engine`   |   ui only: `pytest tests/ui`
