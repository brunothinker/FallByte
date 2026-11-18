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
RPM_STAGE_DIR="$BUILD_DIR/rpm/tree"
FINAL_RPM="$BUILD_DIR/${APP_NAME}_${VERSION}_${ARCH}.rpm"

SPEC_FILE="$PROJECT_ROOT/packaging/rpm/fallbyte.spec"

echo "==> [RPM] Starting build pipeline for ${APP_TITLE} v${VERSION}..."

if [ ! -d "$PYINSTALLER_DIR" ]; then
    echo "ERROR: Compiled binaries not found in $PYINSTALLER_DIR"
    echo "HINT: Run PyInstaller build step before running this packaging script."
    exit 1
fi

if ! command -v rpmbuild &> /dev/null; then
    echo "ERROR: 'rpmbuild' command not found."
    echo "HINT: Install it using 'sudo apt install rpm' (Debian/Ubuntu) or 'sudo dnf install rpm-build' (Fedora)."
    exit 1
fi

# 1. Prepare rpmbuild directory tree
echo "--> [1/4] Preparing rpmbuild environment..."
rm -rf "$RPM_STAGE_DIR"
mkdir -p "$RPM_STAGE_DIR"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
mkdir -p "$RPM_STAGE_DIR/SOURCES/FallByte"

# 2. Stage compiled binaries, multi-size icons, and source assets
echo "--> [2/4] Staging build artifacts and spec file..."
cp -r "$PYINSTALLER_DIR"/* "$RPM_STAGE_DIR/SOURCES/FallByte/"

for SIZE in 48 128 256 512; do
    ICON_DIR="$RPM_STAGE_DIR/SOURCES/icons/${SIZE}x${SIZE}"
    mkdir -p "$ICON_DIR"
    python3 -c "from PIL import Image; Image.open('$ICON_SRC').resize(($SIZE, $SIZE), Image.Resampling.LANCZOS).save('$ICON_DIR/$APP_NAME.png', optimize=True)"
done

if [ -f "$LICENSE_SRC" ]; then
    cp "$LICENSE_SRC" "$RPM_STAGE_DIR/SOURCES/LICENSE"
    cp "$LICENSE_SRC" "$RPM_STAGE_DIR/SOURCES/FallByte/"
fi

if [ -f "$NOTICES_SRC" ]; then
    cp "$NOTICES_SRC" "$RPM_STAGE_DIR/SOURCES/THIRD_PARTY_NOTICES.md"
    cp "$NOTICES_SRC" "$RPM_STAGE_DIR/SOURCES/FallByte/"
fi

if [ -f "$METAINFO_SRC" ]; then
    METAINFO_DST="$RPM_STAGE_DIR/SOURCES/fallbyte.metainfo.xml"
    cp "$METAINFO_SRC" "$METAINFO_DST"
    sed -i -E "s|<release version=\"[^\"]*\" date=\"[^\"]*\" />|<release version=\"${VERSION}\" date=\"${BUILD_DATE}\" />|" "$METAINFO_DST"
fi

cp "$SPEC_FILE" "$RPM_STAGE_DIR/SPECS/"

# 3. Build RPM package passing version macro dynamically
echo "--> [3/4] Compiling RPM package..."
DBPATH_TMP="$(mktemp -d)"

rpmbuild \
  --define "_topdir $RPM_STAGE_DIR" \
  --define "_dbpath $DBPATH_TMP" \
  --define "_version $VERSION" \
  -bb "$RPM_STAGE_DIR/SPECS/fallbyte.spec" > /dev/null

rm -rf "$DBPATH_TMP"

# 4. Locate and relocate generated RPM artifact
echo "--> [4/4] Finalizing RPM package location..."
GENERATED_RPM=$(find "$RPM_STAGE_DIR/RPMS" -type f -name "*.rpm" | head -n 1)

if [ -z "$GENERATED_RPM" ]; then
    echo "ERROR: Failed to find generated RPM in $RPM_STAGE_DIR/RPMS"
    exit 1
fi

mv "$GENERATED_RPM" "$FINAL_RPM"

echo "==> SUCCESS: RPM package built at: $FINAL_RPM"