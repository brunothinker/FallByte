#!/usr/bin/env bash
set -e

source "$(dirname "$0")/common.sh"

echo "[INFO] Locating AppImage artifact..."
APPIMAGE_PATH=$(find /artifacts -type f -name "*.AppImage" 2>/dev/null | head -n 1)

if [ -z "$APPIMAGE_PATH" ]; then
    echo "[ERROR] No .AppImage artifact found in /artifacts."
    exit 1
fi

chmod +x "$APPIMAGE_PATH"

echo "[INFO] Extracting AppImage contents for structural verification..."
cd /tmp
rm -rf squashfs-root
"$APPIMAGE_PATH" --appimage-extract >/dev/null 2>&1 || true

EXTRACTED_DIR="/tmp/squashfs-root"
if [ ! -d "$EXTRACTED_DIR" ]; then
    echo "[ERROR] Failed to extract AppImage."
    exit 1
fi

echo "[INFO] Verifying AppImage bundle structure and binary files..."
if [ ! -f "$EXTRACTED_DIR/AppRun" ]; then
    echo "[ERROR] AppRun entrypoint missing from AppImage root."
    exit 1
fi

if [ ! -x "$EXTRACTED_DIR/usr/bin/FallByte" ]; then
    echo "[ERROR] Main FallByte executable binary missing or not executable."
    exit 1
fi

if [ ! -d "$EXTRACTED_DIR/usr/bin/_internal" ]; then
    echo "[ERROR] PyInstaller _internal dependency directory missing from AppImage."
    exit 1
fi

echo "[INFO] AppImage structural and file integrity check passed successfully."