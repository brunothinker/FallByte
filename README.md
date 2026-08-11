# FallByte

> Drop the weight. Keep the quality.

FallByte is a fast, lightweight, and local-first media optimization tool designed to reclaim disk space without compromising quality or privacy.

---

## About the Project

Most media optimization tools require uploading sensitive files to cloud servers or dealing with ad-heavy web interfaces. **FallByte** runs 100% locally on your machine, processing images and media offline with speed, safety, and precision.

---

## Key Features (Image Module Ready)

The initial release comes fully equipped with the **Image Engine**:

* **Local-First & Private:** Your files never leave your system. No server uploads, no telemetry, no internet required.
* **Batch & Single File Operations:** Process individual files or entire directory structures preserving folder hierarchies.
* **Smart Image Compression:** Reclaim storage using quality controls and advanced PNG quantization (palette reduction) while strictly keeping original file formats.
* **Flexible Image Conversion:** Convert between various formats with automatic background blending for alpha/transparency channels on unsupported formats (e.g., JPEG, BMP).
* **ICO Generation:** Automatic smart scaling (max 256x256) using Lanczos resampling for Windows icons.
* **Safe Session Cancellation:** Interrupt batch processing at any point without leaving orphan or corrupted files behind.

---

## OS Support & Releases

Pre-compiled portable packages (`.zip`) are available for the initial release on the **Releases** page:

| Operating System | Status | Package |
|---|---|---|
| **Windows (x64)** | Supported | Portable `.zip` |
| **Linux (x86_64)** | Supported | Portable `.zip` |
| **macOS** | Planned | Coming in future releases |

---

## Quick Start (Running from Source)

### Prerequisites

* Python 3.10 or higher

### Installation

1. Clone the repository:
   ```bash
   git clone [https://github.com/your-username/FallByte.git](https://github.com/your-username/FallByte.git)
   cd FallByte
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Launch the application:
   ```bash
   python main.py
   ```

---

## Stack

* **Language:** Python
* **UI Framework:** Flet (Flutter for Python)
* **Image Processing:** Pillow (PIL)
* **Media Engine (Upcoming):** FFmpeg

---

## Roadmap

- [x] Core Image Compression Engine (Single & Directory)
- [x] Core Image Conversion Engine (With transparency handling)
- [x] Reactive Flet UI with dark theme & internationalization (i18n)
- [x] Safe I/O session cleanup on process abort
- [ ] Video Compression & Conversion Engine (FFmpeg integration)
- [ ] macOS build support & testing

---

## License

Licensed under the **GNU General Public License v3.0**.