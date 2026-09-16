#!/usr/bin/env bash
set -e

APP_NAME="fallbyte"
APP_TITLE="FallByte"
VERSION="1.0.0"
ARCH="x86_64"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

BUILD_DIR="$PROJECT_ROOT/build"
PYINSTALLER_DIR="$BUILD_DIR/pyinstaller/dist/FallByte"
APPDIR="$BUILD_DIR/appimage/FallByte.AppDir"
FINAL_APPIMAGE="$BUILD_DIR/${APP_NAME}_${VERSION}_${ARCH}.AppImage"

ICON_SRC="$PROJECT_ROOT/resources/icons/fallbyte_icon.png"

echo "==> [AppImage] Starting build pipeline for ${APP_TITLE} v${VERSION}..."

# Verify PyInstaller build directory
if [ ! -d "$PYINSTALLER_DIR" ]; then
    echo "ERROR: Compiled binaries not found in $PYINSTALLER_DIR"
    echo "HINT: Run PyInstaller build step before running this packaging script."
    exit 1
fi

# 1. Fetch reliable appimagetool binary
APPIMAGETOOL="$BUILD_DIR/appimagetool"

if [ -f "$APPIMAGETOOL" ] && [ "$(stat -c%s "$APPIMAGETOOL")" -lt 1000000 ]; then
    rm -f "$APPIMAGETOOL"
fi

if [ ! -f "$APPIMAGETOOL" ]; then
    echo "--> [1/4] Downloading official appimagetool binary..."
    APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    curl -sfSL "$APPIMAGETOOL_URL" -o "$APPIMAGETOOL" || {
        echo "ERROR: Failed to download appimagetool from $APPIMAGETOOL_URL"
        rm -f "$APPIMAGETOOL"
        exit 1
    }
    chmod +x "$APPIMAGETOOL"
fi

# 2. Prepare AppDir directory hierarchy
echo "--> [2/4] Assembling AppDir structure..."
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

# Copy PyInstaller compiled binaries
cp -r "$PYINSTALLER_DIR"/* "$APPDIR/usr/bin/"

# Copy libmpv and ALL its shared dependencies into AppDir
INTERNAL_DIR="$APPDIR/usr/bin/_internal"
mkdir -p "$INTERNAL_DIR"

MPV_PATH=$(ldconfig -p 2>/dev/null | grep -E "libmpv\.so" | head -n 1 | awk '{print $NF}')

if [ -n "$MPV_PATH" ] && [ -f "$MPV_PATH" ]; then
    echo "--> Bundling $MPV_PATH and its dependencies into AppImage..."
    cp -L "$MPV_PATH" "$APPDIR/usr/bin/libmpv.so.2"

    # Rastreia e copia APENAS bibliotecas .so válidas exigidas pela libmpv (ex: libmujs)
    ldd "$MPV_PATH" | awk '/=>/ {print $3}' | grep "^/" | while read -r LIB; do
        if [ -f "$LIB" ]; then
            cp -L -n "$LIB" "$APPDIR/usr/bin/" 2>/dev/null || true
        fi
    done

    # Symlinks de compatibilidade
    ln -sf "libmpv.so.2" "$APPDIR/usr/bin/libmpv.so.1"
    ln -sf "../libmpv.so.2" "$INTERNAL_DIR/libmpv.so.1"
else
    echo "WARNING: libmpv not found on build host. Creating fallback symlink."
    ln -sf "libmpv.so.2" "$INTERNAL_DIR/libmpv.so.1"
fi

# Copy mandatory icons according to XDG / AppImage specifications
cp "$ICON_SRC" "$APPDIR/fallbyte.png"
cp "$ICON_SRC" "$APPDIR/.DirIcon"
cp "$ICON_SRC" "$APPDIR/usr/share/icons/hicolor/256x256/apps/fallbyte.png"

# 3. Generate desktop entry and launcher entrypoint
echo "--> [3/4] Generating AppRun and desktop entry..."
cat <<EOF > "$APPDIR/fallbyte.desktop"
[Desktop Entry]
Name=${APP_TITLE}
Comment=Local-first media optimization tool
Exec=FallByte
Icon=fallbyte
Terminal=false
Type=Application
Categories=AudioVideo;Video;Graphics;
Keywords=media;compress;video;image;optimization;
EOF

cat <<'EOF' > "$APPDIR/AppRun"
#!/bin/sh
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/bin:${HERE}/usr/bin/_internal:${LD_LIBRARY_PATH}"
exec "${HERE}/usr/bin/FallByte" "$@"
EOF

chmod +x "$APPDIR/AppRun"

# 4. Pack into universal AppImage
echo "--> [4/4] Packing AppImage binary..."
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" "$APPDIR" "$FINAL_APPIMAGE"

chmod +x "$FINAL_APPIMAGE"

echo "==> SUCCESS: AppImage built at: $FINAL_APPIMAGE"