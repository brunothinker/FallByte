#!/usr/bin/env bash
# ==============================================================================
# FallByte AppImage Integration Test Script
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

log_info "1. Locating AppImage artifact..."
APPIMAGE_PATH=$(find /artifacts -type f -name "*.AppImage" 2>/dev/null | head -n 1)

if [ -z "$APPIMAGE_PATH" ]; then
    log_error "No .AppImage artifact found in /artifacts."
    exit 1
fi

chmod +x "$APPIMAGE_PATH"

log_info "2. Extracting AppImage contents for structural verification..."
cd /tmp
rm -rf squashfs-root
"$APPIMAGE_PATH" --appimage-extract >/dev/null 2>&1 || true

EXTRACTED_DIR="/tmp/squashfs-root"
if [ ! -d "$EXTRACTED_DIR" ]; then
    log_error "Failed to extract AppImage."
    exit 1
fi

log_info "3. Verifying AppImage bundle structure, desktop entry, and AppStream metadata..."
if [ ! -x "$EXTRACTED_DIR/AppRun" ]; then
    log_error "AppRun entrypoint missing or not executable from AppImage root."
    exit 1
fi

if [ ! -x "$EXTRACTED_DIR/usr/bin/FallByte" ]; then
    log_error "Main FallByte executable binary missing or not executable."
    exit 1
fi

if [ ! -d "$EXTRACTED_DIR/usr/bin/_internal" ]; then
    log_error "PyInstaller _internal dependency directory missing from AppImage."
    exit 1
fi

if [ ! -f "$EXTRACTED_DIR/fallbyte.desktop" ] || [ ! -f "$EXTRACTED_DIR/fallbyte.png" ]; then
    log_error "Root desktop entry or icon missing from AppImage."
    exit 1
fi

if ! grep -q "^StartupWMClass=com.appveyor.flet$" "$EXTRACTED_DIR/fallbyte.desktop"; then
    log_error "StartupWMClass=com.appveyor.flet missing from AppImage fallbyte.desktop"
    exit 1
fi

if [ ! -f "$EXTRACTED_DIR/usr/share/metainfo/io.github.brunothinker.fallbyte.appdata.xml" ]; then
    log_error "AppStream metainfo XML missing from AppImage."
    exit 1
fi

log_info "4. Running CLI checks via extracted AppRun..."
run_cli_checks "$EXTRACTED_DIR/AppRun"

rm -rf "$EXTRACTED_DIR"
log_info "AppImage structural, metadata, and CLI verification passed successfully."