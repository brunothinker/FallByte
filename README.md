# FallByte

> Drop the weight. Keep the quality.

FallByte is a fast, lightweight, and local-first media optimization tool designed to reclaim disk space without compromising quality or privacy.

---

## About the Project

Most media optimization tools require uploading sensitive files to cloud servers or dealing with ad-heavy web interfaces. **FallByte** runs 100% locally on your machine, processing images and videos offline with speed, safety, and precision.

---

## Key Features

FallByte comes fully equipped with high-performance engines for both **Images** and **Videos**:

* **Local-First & Private:** Your files never leave your system. No server uploads, no telemetry, no internet required.
* **Embedded Media Engine (FFmpeg):** Native video conversion and compression powered by standalone FFmpeg binaries—no external system installations required.
* **Smart Video Processing:** 
  * **Conversion:** Standardize videos across major formats (`MP4`, `MKV`, `WEBM`, `MOV`, `AVI`, `WMV`) with automatic multi-threaded codec mapping (`VP9`, `H.264`, `WMV2`).
  * **Compression:** Map quality scales to CRF and bitrate parameters for high space savings.
* **Advanced Image Processing:**
  * **Compression:** Reclaim storage using quality controls and advanced PNG quantization (palette reduction) while strictly keeping original file formats.
  * **Conversion:** Convert between various formats (`PNG`, `JPEG`, `WEBP`, `BMP`, `ICO`) with automatic background blending for transparency channels on unsupported formats.
* **Batch & Single File Operations:** Process individual files or entire directory structures preserving folder hierarchies.
* **Safe Session Cancellation:** Interrupt batch processing at any point without leaving orphan or corrupted files behind.

---

## OS Support & Download

Download the latest pre-compiled portable packages (.zip) for your operating system directly from the Releases page:

| Operating System | Status | Package |
|---|---|---|
| 🐧 **Linux (x86_64)** | Supported | [Download Portable `.zip`](https://github.com/brunothinker/FallByte/releases/latest) |
| 🪟 **Windows (x64)** | Supported | [Download Portable `.zip`](https://github.com/brunothinker/FallByte/releases/latest) |
| 💻 **macOS** | Community Supported | Source execution available |

> **Note:** Check all version updates and source assets directly on the [FallByte Releases Page](https://github.com/brunothinker/FallByte/releases). For macOS, refer to the [Quick Start](#quick-start-running-from-source) section.

---

## Quick Start (Running from Source)

### Prerequisites

* **Python 3.13+** (Recommended version: `Python 3.13.x`)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/brunothinker/FallByte.git
   cd FallByte
   ```

2. Create and activate a virtual environment:
   ```bash
    python3.13 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Launch the application:
   ```bash
   python test_conversion.py
   ```

---

## Stack

* **Language:** Python
* **UI Framework:** Flet (Flutter for Python)
* **Image Processing:** Pillow (PIL)
* **Media Engine (Upcoming):** FFmpeg

---

## License

Licensed under the **GNU General Public License v3.0**.
