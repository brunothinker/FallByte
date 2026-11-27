#!/usr/bin/env bash
set -e

APP_NAME="fallbyte"
APP_TITLE="FallByte"
ARCH="amd64"

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
DEB_STAGING="$BUILD_DIR/deb/${APP_NAME}_${VERSION}_${ARCH}"
FINAL_DEB="$BUILD_DIR/${APP_NAME}_${VERSION}_${ARCH}.deb"

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
mkdir -p "$DEB_STAGING/usr/share/metainfo"
mkdir -p "$DEB_STAGING/usr/share/doc/$APP_NAME"

# 2. Copy compiled artifacts and multi-size icons
echo "--> [2/4] Copying compiled binaries and assets..."
cp -r "$PYINSTALLER_DIR"/* "$DEB_STAGING/usr/lib/$APP_NAME/"

for SIZE in 48 128 256 512; do
    ICON_DIR="$DEB_STAGING/usr/share/icons/hicolor/${SIZE}x${SIZE}/apps"
    mkdir -p "$ICON_DIR"
    python3 -c "from PIL import Image; Image.open('$ICON_SRC').resize(($SIZE, $SIZE), Image.Resampling.LANCZOS).save('$ICON_DIR/$APP_NAME.png', optimize=True)"
done

if [ -f "$METAINFO_SRC" ]; then
    METAINFO_DST="$DEB_STAGING/usr/share/metainfo/fallbyte.metainfo.xml"
    cp "$METAINFO_SRC" "$METAINFO_DST"
    sed -i -E "s|<release version=\"[^\"]*\" date=\"[^\"]*\" />|<release version=\"${VERSION}\" date=\"${BUILD_DATE}\" />|" "$METAINFO_DST"
    chmod 644 "$METAINFO_DST"
fi

if [ -f "$LICENSE_SRC" ]; then
    cp "$LICENSE_SRC" "$DEB_STAGING/usr/share/doc/$APP_NAME/copyright"
    cp "$LICENSE_SRC" "$DEB_STAGING/usr/lib/$APP_NAME/LICENSE"
fi

if [ -f "$NOTICES_SRC" ]; then
    cp "$NOTICES_SRC" "$DEB_STAGING/usr/share/doc/$APP_NAME/"
    cp "$NOTICES_SRC" "$DEB_STAGING/usr/lib/$APP_NAME/"
fi

chmod +x "$DEB_STAGING/usr/lib/$APP_NAME/FallByte"
ln -s "/usr/lib/$APP_NAME/FallByte" "$DEB_STAGING/usr/bin/$APP_NAME"

INTERNAL_DIR="$DEB_STAGING/usr/lib/$APP_NAME/_internal"
mkdir -p "$INTERNAL_DIR"
ln -sf "/usr/lib/x86_64-linux-gnu/libmpv.so.2" "$INTERNAL_DIR/libmpv.so.1"

# 3. Generate desktop launcher, control metadata, and maintainer hooks
echo "--> [3/4] Generating desktop launcher and control metadata..."
cat <<EOF > "$DEB_STAGING/usr/share/applications/$APP_NAME.desktop"
[Desktop Entry]
Name=${APP_TITLE}
Comment=Local-first media optimization and conversion suite
Exec=/usr/bin/$APP_NAME
Icon=$APP_NAME
Terminal=false
Type=Application
Categories=AudioVideo;
StartupWMClass=com.appveyor.flet
Keywords=media;compress;convert;optimization;offline;
EOF

chmod 644 "$DEB_STAGING/usr/share/applications/$APP_NAME.desktop"

INSTALLED_SIZE=$(du -sk "$DEB_STAGING/usr" | cut -f1)

cat <<EOF > "$DEB_STAGING/DEBIAN/control"
Package: $APP_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Installed-Size: $INSTALLED_SIZE
Depends: libgtk-3-0, libgstreamer1.0-0, libgstreamer-plugins-base1.0-0, libmpv2 | libmpv1 | mpv, libheif1
Maintainer: Bruno Henrique <brunothinker@github.com>
Homepage: https://github.com/brunothinker/FallByte
Description: Local-first media optimization and conversion suite
 FallByte is a fast, local-first desktop utility for compressing, optimizing,
 and converting media files completely offline.
 .
 Designed with privacy, batch processing, and workflow efficiency in mind, it
 helps reduce file sizes and standardize formats directly on your machine
 without relying on cloud services.
EOF

cat <<'EOF' > "$DEB_STAGING/DEBIAN/postinst"
#!/bin/sh
set -e

SYSTEM_LIB_DIR="/usr/lib/x86_64-linux-gnu"

if [ -f "$SYSTEM_LIB_DIR/libmpv.so.2" ] && [ ! -f "$SYSTEM_LIB_DIR/libmpv.so.1" ]; then
    ln -sf "$SYSTEM_LIB_DIR/libmpv.so.2" "$SYSTEM_LIB_DIR/libmpv.so.1"
fi

ldconfig

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications >/dev/null 2>&1 || true
fi
EOF

cat <<'EOF' > "$DEB_STAGING/DEBIAN/postrm"
#!/bin/sh
set -e

ldconfig

if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications >/dev/null 2>&1 || true
    fi
fi
EOF

chmod 755 "$DEB_STAGING/DEBIAN/postinst"
chmod 755 "$DEB_STAGING/DEBIAN/postrm"

# 4. Build final Debian package
echo "--> [4/4] Compiling .deb package..."
dpkg-deb --build "$DEB_STAGING" "$FINAL_DEB" > /dev/null

echo "==> SUCCESS: Debian package built at: $FINAL_DEB"