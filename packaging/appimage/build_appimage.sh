#!/usr/bin/env bash
set -e

APP_NAME="fallbyte"
APP_TITLE="FallByte"
ARCH="x86_64"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

VERSION="${1:-${APP_VERSION:-1.0.0}}"
ICON_SRC="${2:-${ICON_SRC:-$PROJECT_ROOT/resources/icons/fallbyte_icon.png}}"
LICENSE_SRC="$PROJECT_ROOT/LICENSE"
NOTICES_SRC="$PROJECT_ROOT/docs/THIRD_PARTY_NOTICES.md"
METAINFO_SRC="$PROJECT_ROOT/packaging/fallbyte.metainfo.xml"
BUILD_DATE="$(date +%Y-%m-%d)"

BUILD_DIR="$PROJECT_ROOT/build"
PYINSTALLER_DIR="$BUILD_DIR/pyinstaller/dist/FallByte"
APPDIR="$BUILD_DIR/appimage/FallByte.AppDir"
FINAL_APPIMAGE="$BUILD_DIR/${APP_NAME}_${VERSION}_${ARCH}.AppImage"

APPIMAGETOOL="$SCRIPT_DIR/appimagetool"

echo "==> [AppImage] Starting build pipeline for ${APP_TITLE} v${VERSION}..."

if [ ! -d "$PYINSTALLER_DIR" ]; then
    echo "ERROR: Compiled binaries not found in $PYINSTALLER_DIR"
    echo "HINT: Run PyInstaller build step before running this packaging script."
    exit 1
fi

# 1. Fetch reliable appimagetool binary if not cached locally
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
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/metainfo"
mkdir -p "$APPDIR/usr/share/doc/$APP_NAME"

# Copy PyInstaller compiled binaries
cp -r "$PYINSTALLER_DIR"/* "$APPDIR/usr/bin/"

# Copy AppStream metadata, license, and third-party notices
if [ -f "$METAINFO_SRC" ]; then
    METAINFO_DST="$APPDIR/usr/share/metainfo/io.github.brunothinker.fallbyte.appdata.xml"
    cp "$METAINFO_SRC" "$METAINFO_DST"
    sed -i -E "s|<release version=\"[^\"]*\" date=\"[^\"]*\" />|<release version=\"${VERSION}\" date=\"${BUILD_DATE}\" />|" "$METAINFO_DST"
fi

if [ -f "$LICENSE_SRC" ]; then
    cp "$LICENSE_SRC" "$APPDIR/usr/bin/LICENSE"
    cp "$LICENSE_SRC" "$APPDIR/usr/share/doc/$APP_NAME/LICENSE"
fi

if [ -f "$NOTICES_SRC" ]; then
    cp "$NOTICES_SRC" "$APPDIR/usr/bin/"
    cp "$NOTICES_SRC" "$APPDIR/usr/share/doc/$APP_NAME/"
fi

# Copy libmpv and non-core dependencies (exclude glibc/system runtime libraries)
INTERNAL_DIR="$APPDIR/usr/bin/_internal"
mkdir -p "$INTERNAL_DIR"

EXCLUDE_REGEX="^(libc|libm|libpthread|libdl|librt|libresolv|libgcc_s|libstdc\+\+|ld-linux|libdrm|libGL|libEGL|libwayland|libX11|libxcb|libxkbcommon|libasound|libpulse|libdbus|libsystemd|libglib-2\.0|libgobject-2\.0|libgio-2\.0)\.so"

MPV_PATH=$(ldconfig -p 2>/dev/null | grep -E "libmpv\.so" | head -n 1 | awk '{print $NF}')

if [ -n "$MPV_PATH" ] && [ -f "$MPV_PATH" ]; then
    echo "--> Bundling $MPV_PATH and non-system dependencies into AppImage..."
    cp -L "$MPV_PATH" "$APPDIR/usr/bin/libmpv.so.2"

    ldd "$MPV_PATH" | awk '/=>/ {print $3}' | grep "^/" | while read -r LIB; do
        LIB_NAME="$(basename "$LIB")"
        if [[ ! "$LIB_NAME" =~ $EXCLUDE_REGEX ]] && [ -f "$LIB" ]; then
            cp -L -n "$LIB" "$APPDIR/usr/bin/" 2>/dev/null || true
        fi
    done

    ln -sf "libmpv.so.2" "$APPDIR/usr/bin/libmpv.so.1"
    ln -sf "../libmpv.so.2" "$INTERNAL_DIR/libmpv.so.1"
else
    echo "WARNING: libmpv not found on build host. Creating fallback symlink."
    ln -sf "libmpv.so.2" "$INTERNAL_DIR/libmpv.so.1"
fi

# Copy root icons and generate multi-size hicolor icons
python3 -c "from PIL import Image; Image.open('$ICON_SRC').resize((256, 256), Image.Resampling.LANCZOS).save('$APPDIR/fallbyte.png', optimize=True)"
cp "$APPDIR/fallbyte.png" "$APPDIR/.DirIcon"

for SIZE in 48 128 256 512; do
    ICON_DIR="$APPDIR/usr/share/icons/hicolor/${SIZE}x${SIZE}/apps"
    mkdir -p "$ICON_DIR"
    python3 -c "from PIL import Image; Image.open('$ICON_SRC').resize(($SIZE, $SIZE), Image.Resampling.LANCZOS).save('$ICON_DIR/fallbyte.png', optimize=True)"
done

# 3. Generate desktop entry and launcher entrypoint
echo "--> [3/4] Generating AppRun and desktop entry..."
cat <<EOF > "$APPDIR/fallbyte.desktop"
[Desktop Entry]
Name=${APP_TITLE}
Comment=Local-first media optimization and conversion suite
Exec=FallByte
Icon=fallbyte
Terminal=false
Type=Application
Categories=AudioVideo;
Keywords=media;compress;convert;optimization;offline;
EOF

cp "$APPDIR/fallbyte.desktop" "$APPDIR/usr/share/applications/fallbyte.desktop"

cat <<'EOF' > "$APPDIR/AppRun"
#!/bin/sh
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/bin:${HERE}/usr/bin/_internal:${LD_LIBRARY_PATH}"
exec "${HERE}/usr/bin/FallByte" "$@"
EOF

chmod +x "$APPDIR/AppRun"

# 4. Pack into universal AppImage with GitHub Releases zsync update info
echo "--> [4/4] Packing AppImage binary..."
UPDATE_INFO="gh-releases-zsync|brunothinker|FallByte|latest|${APP_NAME}_*_${ARCH}.AppImage.zsync"
(
    cd "$BUILD_DIR"
    ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" -u "$UPDATE_INFO" "$APPDIR" "$FINAL_APPIMAGE"
)

chmod +x "$FINAL_APPIMAGE"

echo "==> SUCCESS: AppImage built at: $FINAL_APPIMAGE"