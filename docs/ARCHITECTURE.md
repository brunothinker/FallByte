# FallByte Architecture (Interactive Edition)

Welcome to the interactive architecture reference for **FallByte**. This document serves as a self-contained guide and interactive map of the codebase, designed for contributors, reviewers, and maintainers.

---

## 1. High-Level Overview & System Topology

FallByte enforces a strict separation of concerns between the **Presentation Layer (`ui/`)** and the **Media Processing Engine (`src/`)**. The UI never interacts directly with media libraries or system binaries; instead, **Controllers** mediate user actions, dispatch background jobs, and stream logs/progress back to the interface.

```mermaid
flowchart TD
    Entry["main.py<br/>(Bootstrap & Path Resolution)"] --> UI

    subgraph Presentation ["Presentation Layer (ui/)"]
        UI["Pages & Components<br/>(ui/pages/, ui/components/)"]
        Router["Router & Registry<br/>(router.py, registry.py)"]
        I18n["i18n Engine<br/>(ui/i18n.py)"]
        Ctrl["Controllers<br/>(ui/controllers/)"]

        UI <--> Router
        UI --> I18n
        UI <--> Ctrl
    end

    subgraph Resources ["Static Resources (resources/)"]
        Locales["YAML Locales<br/>(en, pt, es, _template)"]
        Binaries["Bundled Binaries<br/>(FFmpeg)"]
    end

    subgraph Engine ["Core Processing Engine (src/)"]
        Batch["Batch Runner & Progress<br/>(src/utils/)"]
        Img["Image Processor<br/>(src/image/)"]
        Vid["Video Processor<br/>(src/video/)"]
        Aud["Audio Processor<br/>(src/audio/)"]
        Config["Config Manager<br/>(config_manager.py)"]

        Batch --> Img
        Batch --> Vid
        Batch --> Aud
    end

    I18n -.->|Loads| Locales
    Ctrl -->|Dispatches Jobs & Reads Logs| Batch
    Ctrl -->|Single File Ops| Img
    Ctrl -->|Single File Ops| Vid
    Ctrl -->|Single File Ops| Aud
    Vid -->|Locates| Binaries
    Aud -->|Locates| Binaries
    Entry -.->|Initializes| Config
```

---

## 2. Directory Structure Explorer

Explore the module hierarchy of the project layout:

```text
FallByte/
├── main.py                  # App entry point & environment bootstrap
├── FallByte.spec            # PyInstaller build configuration
├── packaging/               # Distro packaging scripts & Docker test runners
├── resources/
│   ├── bin/                 # Bundled platform-specific binaries (FFmpeg)
│   ├── icons/               # Application icons (.ico, .png)
│   └── locales/             # YAML translation files (en, pt, es, _template)
├── src/                     # Core domain & media processing engine
│   ├── formats.py           # Supported file extensions and format definitions
│   ├── image/               # Image compression/conversion & transparency utils
│   ├── video/               # Video compression/conversion & FFmpeg wrappers
│   ├── audio/               # Audio compression/conversion & FFmpeg stream wrappers
│   └── utils/               # Batch runner, config manager, naming, & cleanup
├── tests/                   # Pytest suite separated into audio/, batch/, image/, utils/, ui/, video/
└── ui/                      # Presentation & interaction layer
    ├── app_layout.py        # Main window shell & navigation frame
    ├── router.py            # View routing and navigation state
    ├── registry.py          # Page and controller registration
    ├── theme.py             # Color palettes, typography, and styling tokens
    ├── i18n.py              # Locale loader and translation lookup engine
    ├── components/          # Reusable UI widgets (pickers, quality selectors)
    ├── controllers/         # Mediators connecting UI actions to src/ workers
    ├── pages/               # Screen definitions (Home, Hub, Image/Video/Audio views)
    └── utils/               # UI-specific helpers (path formatting, log capture)
```

---

## 3. Core Subsystems & Responsibilities

### Media Engine (`src/`)

- **Single vs. Batch Operations**: `src/image/`, `src/video/`, and `src/audio/` split operations into `*_file_*` (single target) and `*_directory_*` (batch target) modules.
- **Batch Execution (`src/utils/batch_runner.py`)**: Orchestrates multi-file queues, tracks progress (`src/utils/progress.py`), and handles safe output naming (`src/utils/output_naming.py`). `run_batch` returns a statistics dictionary (`total_files`, `success`, `failed`, `cancelled`, `cleaned_files_count`, and so on). Failures are reported at three levels:
  - **Per-file failures**: Destination construction, processing, and output checks are guarded per file. An ordinary exception is logged with the source path and counted once as failed; a processor returning `False` also counts as failed. The runner then attempts a completed progress update and continues to the next file. If the progress callback raises an ordinary exception, the batch stops with `stats["error"]`.
  - **Cancellation**: `InterruptedError` is never treated as a file failure. It is re-raised to the batch-level handler, which sets `cancelled`, stops processing, and runs `safe_cleanup_session_files`. Cleanup removes the newly created outputs the runner tracked: outputs of successful files and outputs left by a file that raised an ordinary exception or was interrupted, provided the destination did not already exist before that file was processed. Pre-existing destination files are never deleted. Outputs are only removed on cancellation, not when a file fails. If cancellation happens before the session output folder exists (for example while scanning), there is nothing to clean up.
  - **Batch-level errors (`stats["error"]`)**: An ordinary exception outside the per-file handler ends the batch and is returned as `stats["error"]` (the exception message, or the exception class name if it has none), together with the elapsed time. This covers scanning, sorting, and creating the session output folder (no files are processed in those cases), an ordinary exception raised by the progress callback (either the start-of-file or the completed update), and any other unexpected ordinary exception in the batch machinery. Files that finished before a batch-level error keep their counts, so `success` can be greater than zero alongside `error`; a progress-callback failure is not counted as a file failure. A batch-level error is not a cancellation (`cancelled` stays `False`) and does not trigger output cleanup. `InterruptedError` raised by a progress callback still cancels. An empty scan is unchanged: it returns `no_files` rather than `error`.
- **Binary Management (`src/utils/binary_manager.py`)**: Locates system or bundled `ffmpeg` binaries across OS environments and frozen builds.

### UI & Controllers (`ui/`)

- **Pages (`ui/pages/`)**: Declarative views responsible only for layout and user input events.
- **Controllers (`ui/controllers/`)**: Inherit from `BaseController`. They validate user input, dispatch background tasks to `src/`, capture logs (`ui/utils/log_capture.py`), and push state updates back to the pages.
  - **Returned batch errors**: In all six batch methods (image, video, and audio compression and conversion), the non-cancelled path checks `summary.get("error")` before empty-input (`no_files`) and normal success handling. When an error is returned, the controller logs it, shows the existing translated `msg_error` status in the error color, and skips the success message, the full progress bar, and the success summary dialog. The `finally` block still stops log redirection and restores the idle controls. The status shows the generic message; the specific error text is in the log. A cancelled batch is handled as before and takes precedence over any error handling.
- **Navigation (`router.py` & `registry.py`)**: Decouples page instantiation from navigation triggers.

### Internationalization (`ui/i18n.py` & `resources/locales/`)

- All user-facing strings are externalized into YAML files inside `resources/locales/` (`en.yaml`, `pt.yaml`, `es.yaml`).
- `ui/i18n.py` loads the active locale (persisted via `src/utils/config_manager.py`) and provides fallback resolution to English (`en.yaml`) if a key is missing.

---

## 4. Contributor Rules & PR Checklist

1. **Architectural Boundaries**: Keep all processing logic inside `src/`. Never import `ui` modules inside `src/`.
2. **Code Style**: Follow PEP 8 strictly as enforced by `ruff`. Run `ruff check .` before submitting.
3. **Testing**: Every new feature or bug fix must include corresponding unit/integration tests under `tests/`. Batch failure handling (issue #50) is covered by these regression tests:
   - `tests/batch/test_run_batch.py`: verifies continuation and accurate counts after file errors, cancellation and output cleanup, preservation of pre-existing paths, progress-callback failures, and setup failures.
   - `tests/ui/test_controller_execution.py`: verifies returned-error handling across all six controllers, including error display, suppression of success dialogs, and restoration of controls and standard streams.
4. **i18n Minimum**: When adding UI strings, **`en.yaml` and `_template.yaml` MUST be updated**.
