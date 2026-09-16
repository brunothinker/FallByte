#!/usr/bin/env bash
set -e

APP_NAME="fallbyte"
APP_TITLE="FallByte"
VERSION="1.0.0"
ARCH="amd64"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

BUILD_DIR="$PROJECT_ROOT/build"
PYINSTALLER_DIR="$BUILD_DIR/pyinstaller/dist/FallByte"
DEB_STAGING="$BUILD_DIR/deb/${APP_NAME}_${VERSION}_${ARCH}"
FINAL_DEB="$BUILD_DIR/${APP_NAME}_${VERSION}_${ARCH}.deb"

ICON_SRC="$PROJECT_ROOT/resources/icons/fallbyte_icon.png"

echo "==> [Debian] Starting build pipeline for ${APP_TITLE} v${VERSION}..."

if [ ! -d "$PYINSTALLER_DIR" ]; then
    echo "ERROR: Compiled binaries not found in $PYINSTALLER_DIR"
    exit 1
fi

# 1. Prepare staging directory structure
echo "--> [1/4] Preparing filesystem staging hierarchy..."
rm -rf "$DEB_STAGING"
mkdir -p "$DEB_STAGING/DEBIAN"
mkdir -p "$DEB_STAGING/usr/bin"
mkdir -p "$DEB_STAGING/usr/lib/$APP_NAME"
mkdir -p "$DEB_STAGING/usr/share/applications"
mkdir -p "$DEB_STAGING/usr/share/icons/hicolor/256x256/apps"

# 2. Copy compiled artifacts
echo "--> [2/4] Copying compiled binaries and assets..."
cp -r "$PYINSTALLER_DIR"/* "$DEB_STAGING/usr/lib/$APP_NAME/"
cp "$ICON_SRC" "$DEB_STAGING/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png"

chmod +x "$DEB_STAGING/usr/lib/$APP_NAME/FallByte"
ln -s "/usr/lib/$APP_NAME/FallByte" "$DEB_STAGING/usr/bin/$APP_NAME"

INTERNAL_DIR="$DEB_STAGING/usr/lib/$APP_NAME/_internal"
mkdir -p "$INTERNAL_DIR"
ln -sf "/usr/lib/x86_64-linux-gnu/libmpv.so.2" "$INTERNAL_DIR/libmpv.so.1"

# 3. Generate desktop launcher, control metadata, and postinst hook
echo "--> [3/4] Generating desktop launcher and control metadata..."
cat <<EOF > "$DEB_STAGING/usr/share/applications/$APP_NAME.desktop"
[Desktop Entry]
Name=${APP_TITLE}
Comment=Local-first media optimization tool
Exec=/usr/bin/$APP_NAME
Icon=$APP_NAME
Terminal=false
Type=Application
Categories=AudioVideo;Video;Graphics;
Keywords=media;compress;video;image;optimization;
EOF

chmod 644 "$DEB_STAGING/usr/share/applications/$APP_NAME.desktop"

cat <<EOF > "$DEB_STAGING/DEBIAN/control"
Package: $APP_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Depends: libgtk-3-0, libgstreamer1.0-0, libgstreamer-plugins-base1.0-0, libmpv2 | libmpv1 | mpv
Maintainer: Bruno Henrique <brunothinker@github.com>
Description: Local-first media optimization tool for images and videos.
EOF

# Hook de pós-instalação para criar o symlink no diretório global de bibliotecas do sistema
cat <<'EOF' > "$DEB_STAGING/DEBIAN/postinst"
#!/bin/sh
set -e

SYSTEM_LIB_DIR="/usr/lib/x86_64-linux-gnu"

if [ -f "$SYSTEM_LIB_DIR/libmpv.so.2" ] && [ ! -f "$SYSTEM_LIB_DIR/libmpv.so.1" ]; then
    ln -sf "$SYSTEM_LIB_DIR/libmpv.so.2" "$SYSTEM_LIB_DIR/libmpv.so.1"
fi

ldconfig
EOF

chmod 755 "$DEB_STAGING/DEBIAN/postinst"

# 4. Build final Debian package
echo "--> [4/4] Compiling .deb package..."
dpkg-deb --build "$DEB_STAGING" "$FINAL_DEB" > /dev/null

echo "==> SUCCESS: Debian package built at: $FINAL_DEB"