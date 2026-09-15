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

Choose the appropriate package for your operating system on our official download page or via GitHub Releases:

| Operating System | Supported Formats | Status |
|---|---|---|
| 🐧 **Ubuntu / Debian / Mint** | Native `.deb` Package | Supported |
| 🎩 **Fedora / RHEL / openSUSE** | Native `.rpm` Package | Supported |
| 🚀 **Arch / Universal Linux** | Portable `.AppImage` | Supported |
| 🪟 **Windows (x64)** | Portable `.zip` | Supported |
| 💻 **macOS** | Source execution only | Community Supported |

> 📥 **[Get FallByte for your OS (Official Download Page)](https://brunothinker.github.io/FallByte/)**
> 
> *Prefer raw build artifacts? You can also browse all compiled files on the [GitHub Releases Page](https://github.com/brunothinker/FallByte/releases).*

---

## Development

For local development or running from source:

```bash
git clone https://github.com/brunothinker/FallByte.git
cd FallByte
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```
---

## Stack

* **Language:** Python
* **UI Framework:** Flet (Flutter for Python)
* **Image Processing:** Pillow (PIL)
* **Media Engine (Upcoming):** FFmpeg (Static Binaries)

---

## License

Licensed under the **GNU General Public License v3.0**.
