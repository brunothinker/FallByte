# Software Architecture — FallByte

## 1. Architecture Overview and Directory Tree

**FallByte** is a modular desktop application for high-performance media processing, conversion, and compression. The system adopts a strictly decoupled architecture following the **MVC / Reactive** pattern, completely separating the Graphical User Interface (UI) from business rules and file handling (Core Engine).

```text
FallByte/
├── ARCHITECTURE.md
├── FallByte.spec           # PyInstaller build specification
├── LICENSE
├── README.md
├── THIRD_PARTY_NOTICES.md
├── main.py
├── requirements.txt
├── packaging/              # Build scripts and package bundlers
│   ├── appimage/           # AppImage packaging assets and scripts
│   │   └── build_appimage.sh
│   ├── deb/                # Debian (.deb) packaging scripts
│   │   └── build_deb.sh
│   ├── rpm/                # RPM package specifications and build scripts
│   │   └── build_rpm.sh
│   └── build.sh            # Master packaging orchestrator
├── resources/              # Third-party binaries (FFmpeg) and static assets
│   ├── bin/
│   │   ├── linux/
│   │   │   └── ffmpeg
│   │   ├── mac/
│   │   └── windows/
│   │       └── ffmpeg.exe
│   └── icons/
│       ├── fallbyte_icon.ico
│       └── fallbyte_icon.png
├── src/                    # Core Engine: Business logic and I/O processing
│   ├── image/              # Image processing domain
│   │   ├── compression/    # Image compression engine and orchestrator
│   │   ├── conversion/     # Image conversion engine and orchestrator
│   │   └── utils/          # Pre-flight analysis, opacity removal, scanner, metrics
│   ├── utils/              # Shared infrastructure utilities (Config manager)
│   └── video/              # Video processing domain
│       ├── compression/    # Video compression engine and orchestrator
│       ├── conversion/     # Video conversion engine and orchestrator
│       └── utils/          # Binary manager (FFmpeg), video progress, scanner, cleanup
└── ui/                     # Reactive graphical user interface (Flet / Flutter for Python)
    ├── components/         # Encapsulated visual components
    ├── controllers/        # State controllers and asynchronous bridge
    ├── pages/              # Primary views/pages (Image, Video & Hub)
    ├── utils/              # UI utilities and converter support
    ├── app_layout.py       # Global frame, Dynamic header, and Navigation stack
    ├── i18n.py             # Internationalization engine (i18n)
    ├── router.py           # Central screen mapper and router
    └── theme.py            # Design System (Colors, Typography, and Measurements)
```

---

## 2. User Interface Subsystem (`ui/`)

### A. UI Layer Overview

The `ui/` subsystem implements a reactive, event-driven, and decoupled architecture based on **Flet (Flutter for Python)**. The interface layer is exclusively responsible for the user experience, visual state management, route pre-validation, and asynchronous delegation of heavy I/O operations and media manipulation to the Core Engine (`src/`).

### B. UI Component Diagram and MVC Flow

```mermaid
graph TD

subgraph UIShell["Shell & Routing"]
    LAYOUT["app_layout.py"]
    ROUTER["router.py"]
    I18N["i18n.py"]
end

subgraph Views["Pages (Views)"]
    PAGE_HOME["home_page.py"]
    PAGE_HUB["media_hub_page.py"]
    IMG_COMP_PAGE["image_compression_page.py"]
    IMG_CONV_PAGE["image_conversion_page.py"]
    VID_COMP_PAGE["video_compression_page.py"]
    VID_CONV_PAGE["video_conversion_page.py"]
end

subgraph Components["Reusable Components"]
    CARD_IO["io_picker_card.py"]
    Q_SELECT["quality_selector.py"]
    DIALOGS["dialog_utils.py"]
end

subgraph Controllers["Controllers Layer"]
    IMG_COMP_CTRL["ImageCompressionController"]
    IMG_CONV_CTRL["ImageConversionController"]
    VID_COMP_CTRL["VideoCompressionController"]
    VID_CONV_CTRL["VideoConversionController"]
end

subgraph CoreEngine["Core Engine (src/)"]
    IMG_ENGINE["src.image.*"]
    VID_ENGINE["src.video.*"]
end

LAYOUT -->|"Navigation"| ROUTER
ROUTER -->|"Builds"| PAGE_HOME
ROUTER -->|"Builds"| PAGE_HUB
ROUTER -->|"Builds"| IMG_COMP_PAGE
ROUTER -->|"Builds"| IMG_CONV_PAGE
ROUTER -->|"Builds"| VID_COMP_PAGE
ROUTER -->|"Builds"| VID_CONV_PAGE

LAYOUT -.->|"Localization"| I18N
Views -.->|"Localized Strings"| I18N

IMG_COMP_PAGE -->|"Delegates Events"| IMG_COMP_CTRL
IMG_CONV_PAGE -->|"Delegates Events"| IMG_CONV_CTRL
VID_COMP_PAGE -->|"Delegates Events"| VID_COMP_CTRL
VID_CONV_PAGE -->|"Delegates Events"| VID_CONV_CTRL

IMG_COMP_PAGE -.->|"Uses"| Q_SELECT
VID_COMP_PAGE -.->|"Uses"| Q_SELECT
IMG_COMP_PAGE -.->|"Uses"| CARD_IO
IMG_CONV_PAGE -.->|"Uses"| CARD_IO
VID_COMP_PAGE -.->|"Uses"| CARD_IO
VID_CONV_PAGE -.->|"Uses"| CARD_IO

IMG_COMP_CTRL -->|"Async Thread"| IMG_ENGINE
IMG_CONV_CTRL -->|"Async Thread"| IMG_ENGINE
VID_COMP_CTRL -->|"Async Thread"| VID_ENGINE
VID_CONV_CTRL -->|"Async Thread"| VID_ENGINE

Controllers -->|"Displays Summary Modal"| DIALOGS
```

### C. UI Architectural Patterns

1. **Historical Routing and Reactive Layout (`app_layout.py` & `router.py`):**
   * **Navigation Stack (`navigation_stack`):** Maintains the full history of visited routes to enable consistent "Back" navigation through the sticky header.
   * **Overlay Cleanup (`cleanup_page_overlays`):** Automatically purges open dialogs, pending popups, and `FilePicker` instances attached to `page.overlay` on every screen transition, preventing memory leaks and orphan control exceptions.
   * **Centralized Mapping:** The `ROUTE_REGISTRY` dictionary decouples navigation calls via string keys (e.g., `"image_hub"`, `"image_compression"`), binding them to their respective view builder functions.

2. **State Controllers (`controllers/`):**
   * **Concurrent Window Prevention (`picker_active`):** Controls the opening cycle of native OS pickers, blocking duplicate triggers on rapid double clicks.
   * **Pre-flight File Analysis:** Evaluates files within selected directories for incompatible extensions before invoking heavy processors, displaying informative `AlertDialog` popups.
   * **Dual Operation Mode:** Transparently evaluates whether the `selected_input` is a single file (`is_file()`) or a directory, triggering the corresponding APIs in `src/image/` or `src/video/`.

### D. Sequence Diagram: UI Abort and Cancellation

```mermaid
sequenceDiagram

actor User as User
participant Controller as Controller
participant Dialog as Abort Modal
participant Engine as Batch Engine (src)
participant Cleanup as safe_cleanup_session_files

User->>Controller: Clicks Stop Process
Controller->>Dialog: Renders Confirmation Modal

alt User confirms abort
    User->>Dialog: Clicks Stop and Delete
    Dialog->>Controller: Sets abort_requested = True
    Engine->>Controller: Progress Callback
    Controller-->>Engine: Raises InterruptedError
    Engine->>Cleanup: Purges created files and empty subfolders
    Cleanup-->>Engine: Returns total cleaned
    Engine-->>Controller: Returns stats with cancelled=True
    Controller->>User: Displays message and cleaned file count
else User decides to continue
    User->>Dialog: Clicks Keep Processing
    Dialog->>Controller: Closes Modal and Keeps Running
end
```

### E. Design System and Componentization

- **QualitySelector (`quality_selector.py`):** Self-contained reactive component inheriting from `ft.Column`. Implements real-time bidirectional synchronization between a `Slider` (1-100) control and a `TextField` with focus-loss validation (`on_blur`).
- **IOPickerCard (`io_picker_card.py`):** Encapsulates responsive cards with ink ripple effects for click visual feedback and clean display of the selected directory/file path.
- **DialogUtils (`dialog_utils.py`):** Manages the post-execution summary modal (`show_summary_dialog`), computing overall space reduction statistics (original vs reduced bytes), success/failure counts, and expandable log details with contextual color support.
- **Global Theme (`theme.py`):** Centralizes design tokens maintaining visual consistency (`COLOR_CARD_BG`, `COLOR_PRIMARY`, `COLOR_SUCCESS`, `COLOR_ERROR`, `FORM_WIDTH = 550px`).

---

## 3. Core Engine (`src/`)

### A. Core Layer Overview

The `src/` directory concentrates business logic, low-level media processors, and infrastructure utilities. It adheres strictly to the **Single Responsibility Principle (SRP)** and **Total UI Decoupling**, allowing any orchestrator (GUI, CLI, or Test Suites) to run processing routines synchronously or asynchronously.

```text
src/
├── image/                  # Image processing domain
│   ├── compression/        # Image compression engine and orchestrator
│   ├── conversion/         # Image conversion engine and orchestrator
│   └── utils/              # Pre-flight analysis, opacity removal, scanner, metrics
├── utils/                  # Shared infrastructure utilities (Config manager)
└── video/                  # Video processing domain
    ├── compression/        # Video compression engine and orchestrator
    ├── conversion/         # Video conversion engine and orchestrator
    └── utils/              # Binary manager (FFmpeg), video progress, scanner, cleanup
```

### B. Core Component Diagram (`src`)

```mermaid
graph TD

subgraph UI["Interface Layer"]
    CTRL["Controllers / UI Workers"]
end

subgraph ImageDomain["Image Module"]
    IMG_DIR_COMP["image/directory_compression.py"]
    IMG_FILE_COMP["image/file_compression.py"]
    IMG_DIR_CONV["image/directory_conversion.py"]
    IMG_FILE_CONV["image/file_conversion.py"]
    IMG_TRANS["remove_transparency.py"]
    IMG_SCAN["image_scanner.py"]
    IMG_CLEAN["image_cleanup.py"]
end

subgraph VideoDomain["Video Module (FFmpeg Engine)"]
    VID_DIR_COMP["video/directory_compression.py"]
    VID_FILE_COMP["video/file_compression.py"]
    VID_DIR_CONV["video/directory_conversion.py"]
    VID_FILE_CONV["video/file_conversion.py"]
    FFMPEG_HELP["ffmpeg_utils.py"]
    BIN_MGR["binary_manager.py"]
    VID_SCAN["video_scanner.py"]
    VID_CLEAN["video_cleanup.py"]
end

subgraph InfraUtils["Infrastructure & Config"]
    CFG_MGR["src/utils/config_manager.py"]
end

CTRL -->|"1. Configuration"| CFG_MGR

CTRL -->|"2. Image Batch/File"| IMG_DIR_COMP
CTRL -->|"2. Image Batch/File"| IMG_DIR_CONV
IMG_DIR_COMP -->|"Scans Files"| IMG_SCAN
IMG_DIR_CONV -->|"Scans Files"| IMG_SCAN
IMG_DIR_COMP -->|"Iterates Items"| IMG_FILE_COMP
IMG_DIR_CONV -->|"Iterates Items"| IMG_FILE_CONV
IMG_FILE_CONV -->|"Flattens Alpha"| IMG_TRANS
IMG_DIR_COMP -->|"On Cancel"| IMG_CLEAN
IMG_DIR_CONV -->|"On Cancel"| IMG_CLEAN

CTRL -->|"3. Video Batch/File"| VID_DIR_COMP
CTRL -->|"3. Video Batch/File"| VID_DIR_CONV
VID_DIR_COMP -->|"Scans Files"| VID_SCAN
VID_DIR_CONV -->|"Scans Files"| VID_SCAN
VID_DIR_COMP -->|"Iterates Items"| VID_FILE_COMP
VID_DIR_CONV -->|"Iterates Items"| VID_FILE_CONV
VID_FILE_COMP -->|"Muxing & Probing"| FFMPEG_HELP
VID_FILE_CONV -->|"Muxing & Probing"| FFMPEG_HELP
FFMPEG_HELP -->|"Locates Executable"| BIN_MGR
VID_DIR_COMP -->|"On Cancel"| VID_CLEAN
VID_DIR_CONV -->|"On Cancel"| VID_CLEAN
```

### C. Sequence Diagram: Batch Execution and Safe Cancellation

```mermaid
sequenceDiagram

actor User as User
participant Worker as Worker Thread
participant DirOrch as Directory Processor
participant FileProc as File Processor / FFmpeg
participant Cleanup as safe_cleanup_session_files

User->>Worker: Start Processing
Worker->>DirOrch: Execute batch

loop For each file
    DirOrch->>FileProc: Process individual file
    FileProc-->>DirOrch: Success or Failure
    DirOrch-->>Worker: ProgressInfo Callback
    
    alt User Clicks Cancel
        User->>Worker: Abort Session
        Worker->>DirOrch: Raises InterruptedError
        DirOrch->>Cleanup: safe_cleanup_session_files
        Note over Cleanup: Purges ONLY created destination files and empty subfolders
        Cleanup-->>DirOrch: Returns cleaned file count
        DirOrch-->>Worker: Returns stats with cancelled=True
    end
end
```

### D. Business Rules and Media Handling

#### Conversion Module (`src/image/conversion/` & `src/video/conversion/`)
- **Image Domain:** Standardize files to a single target format (`JPEG`, `PNG`, `WEBP`, `BMP`, `TIFF`, `GIF`, `ICO`, `PPM`, `PDF`).
  - **Alpha Channel / Transparency:** When target format lacks opacity support (e.g., `JPEG`, `BMP`), `remove_transparency()` flattens the image over a solid background color chosen by the user (`background_color`, default `#FFFFFF`).
  - **ICO Format Handling:** Forces dimension limits (256x256 pixels max) using `LANCZOS` resampling and transparent square padding.
- **Video Domain:** Converts videos (`MP4`, `MKV`, `WEBM`, `MOV`, `AVI`, `WMV`) using multi-tiered fallback strategies:
  1. Pure stream remux (lossless & instant) when codecs are compatible.
  2. Video copy + audio re-encode when only audio codec is rejected.
  3. Safe full re-encode using `yuv420p` pixel format and even dimensions.
  4. Rescue re-encode with timestamp regeneration for damaged files.

#### Compression Module (`src/image/compression/` & `src/video/compression/`)
- **Image Domain:** Reduces byte size while **strictly preserving the original format**.
  - **PNG Quantization (TinyPNG style):** For `PNG` images with quality < 90, palette reduction down to 256 colors via `FASTOCTREE` (with Alpha) or `MEDIANCUT` (without Alpha).
  - **Uncompressible Protection:** Formats that cannot be safely re-encoded without losing animations or embedded sizes (`BMP`, `PPM`, `GIF`, `ICO`) are kept untouched.
- **Video Domain:** Maps quality percentage (1-100%) to CRF (for `libx264`/`libvpx-vp9`) or `qscale` (for `wmv2`), keeping the original file if the result turns out larger than the input.

### E. I/O Isolation Guarantee (`safe_cleanup_session_files`)

The cleanup utilities (`image_cleanup.py` and `video_cleanup.py`) guarantee that mid-process cancellations **never result in data loss or corruption**:

1. **Restricted Scope:** Only instances present in `created_destination_files` are targeted for deletion.
2. **Root Protection:** The check `dst_file.parent != root_output_dir` prevents the root output directory selected by the user from being removed.
3. **Clean Recursive Cleanup:** Only subdirectories created in the current session that remain completely empty after file removal are deleted.

---

## 4. Additional Resources and Testing (`resources/` & `tests/`)

### A. Assets and Binaries (`resources/`)
- **`resources/bin/`:** Stores pre-compiled platform binaries (Linux, macOS, Windows) for external tools such as `FFmpeg` (`resources/bin/win/ffmpeg.exe`, `resources/bin/linux/ffmpeg`), used by the video module without requiring global system installation.
- **`resources/icons/`:** Contains static visual assets for the application (`fallbyte_icon.ico` and `fallbyte_icon.png`).

### B. Code Quality and Test Suite (`tests/`)
- **Structural Parity:** The test directory closely mirrors the `src/` tree (`tests/image/`, `tests/utils/`, `tests/video/`).
- **Side-Effect Isolation:** Executes automated suites via `pytest` for rigorous validation of conversion ratios, metadata preservation, failure cleanup logic, and pre-flight checks.