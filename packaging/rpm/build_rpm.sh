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
RPM_STAGE_DIR="$BUILD_DIR/rpm/tree"
FINAL_RPM="$BUILD_DIR/${APP_NAME}_${VERSION}_${ARCH}.rpm"

ICON_SRC="$PROJECT_ROOT/resources/icons/fallbyte_icon.png"
SPEC_FILE="$PROJECT_ROOT/packaging/rpm/fallbyte.spec"

echo "==> [RPM] Starting build pipeline for ${APP_TITLE} v${VERSION}..."

# Verify PyInstaller build directory
if [ ! -d "$PYINSTALLER_DIR" ]; then
    echo "ERROR: Compiled binaries not found in $PYINSTALLER_DIR"
    echo "HINT: Run PyInstaller build step before running this packaging script."
    exit 1
fi

# Verify rpmbuild tool availability
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

# 2. Stage compiled binaries and source assets
echo "--> [2/4] Staging build artifacts and spec file..."
cp -r "$PYINSTALLER_DIR"/* "$RPM_STAGE_DIR/SOURCES/FallByte/"
cp "$ICON_SRC" "$RPM_STAGE_DIR/SOURCES/fallbyte_icon.png"
cp "$SPEC_FILE" "$RPM_STAGE_DIR/SPECS/"

# 3. Build RPM package
echo "--> [3/4] Compiling RPM package..."
DBPATH_TMP="$(mktemp -d)"

rpmbuild \
  --define "_topdir $RPM_STAGE_DIR" \
  --define "_dbpath $DBPATH_TMP" \
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