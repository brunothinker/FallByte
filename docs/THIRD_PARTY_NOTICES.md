# Third-Party Notices and Licenses

This application bundles external third-party software components and standalone binaries.

---

## 1. FFmpeg (Bundled Binary)

- **Name:** FFmpeg Static Build
- **Version:** 7.0.2-static
- **Build Origin:** John Van Sickle (https://johnvansickle.com/ffmpeg/)
- **License:** GNU General Public License v3.0 (GPLv3)
- **Source Code:** [FFmpeg Source Releases](https://ffmpeg.org/download.html) / [John Van Sickle Build Scripts](https://johnvansickle.com/ffmpeg/)
- **Description:** Standalone FFmpeg static binary used for video/audio re-encoding, stream copying, and media compression.
- **Build Configuration:**
  ```text
  --enable-gpl --enable-version3 --enable-static --disable-debug --disable-ffplay
  --disable-indev=sndio --disable-outdev=sndio --cc=gcc --enable-fontconfig --enable-frei0r
  --enable-gnutls --enable-gmp --enable-libgme --enable-gray --enable-libaom --enable-libfribidi
  --enable-libass --enable-libvmaf --enable-libfreetype --enable-libmp3lame --enable-libopencore-amrnb
  --enable-libopencore-amrwb --enable-libopenjpeg --enable-librubberband --enable-libsoxr
  --enable-libspeex --enable-libsrt --enable-libvorbis --enable-libopus --enable-libtheora
  --enable-libvidstab --enable-libvo-amrwbenc --enable-libvpx --enable-libwebp --enable-libx264
  --enable-libx265 --enable-libxml2 --enable-libdav1d --enable-libxvid --enable-libzvbi --enable-libzimg

---

## 2. Python Dependencies

### Flet
- **License:** Apache License 2.0
- **Source:** https://github.com/flet-dev/flet

### Pillow (PIL)
- **License:** HPND License (Historical Permission Notice and Disclaimer)
- **Source:** https://github.com/python-pillow/Pillow

### PyYAML
- **License:** MIT License
- **Source:** https://github.com/yaml/pyyaml