#!/usr/bin/env bash
# ==============================================================================
# FallByte Release Packaging Orchestrator
# ==============================================================================
# Usage:
#   ./build.sh [OPTIONS] [VERSION]
#
# Options:
#   --version=<version>, -v <version>   Specify the target release version (e.g., 2.0.0).
#   --help, -h                          Show this help message and exit.
#
# Examples:
#   ./build.sh --version=2.0.0
#   ./build.sh -v 2.0.0
#   ./build.sh 2.0.0
#   ./build.sh                          (Interactive prompt)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

BUILD_DIR="$PROJECT_ROOT/build"
PYINSTALLER_DIR="$BUILD_DIR/pyinstaller"
SPEC_FILE="$PROJECT_ROOT/packaging/rpm/fallbyte.spec"
MAIN_PY="$PROJECT_ROOT/main.py"

show_help() {
    cat <<EOF
FallByte Release Packaging Orchestrator

Usage:
  $(basename "$0") [OPTIONS] [VERSION]

Options:
  --version=<version>, -v <version>   Specify target release version (e.g., 2.0.0).
  --help, -h                          Show this help menu and exit.

Examples:
  $(basename "$0") --version=2.0.0
  $(basename "$0") -v 2.0.0
  $(basename "$0") 2.0.0
  $(basename "$0")                     (Triggers interactive prompt)
EOF
}

# 1. Parse CLI arguments for version or help requests
TARGET_VERSION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)
      show_help
      exit 0
      ;;
    --version=*)
      TARGET_VERSION="${1#*=}"
      shift
      ;;
    --version|-v)
      if [[ -n "$2" && "$2" != -* ]]; then
        TARGET_VERSION="$2"
        shift 2
      else
        echo "ERROR: Option '$1' requires a valid version string."
        exit 1
      fi
      ;;
    --*)
      TARGET_VERSION="${1#--}"
      shift
      ;;
    *)
      TARGET_VERSION="$1"
      shift
      ;;
  esac
done

# Ensure PyInstaller executable is present in PATH
if ! command -v pyinstaller &> /dev/null; then
    echo "ERROR: 'pyinstaller' executable not found in current PATH."
    echo "HINT: Please activate your active Python environment (e.g., 'conda activate FallByteVenv')."
    exit 1
fi

# Cleanup handler to automatically restore main.py back to "dev" on exit or error
restore_main_py() {
    echo "--> Restoring APP_VERSION in main.py back to 'dev'..."
    sed -i -E 's/^(APP_VERSION\s*=\s*").*/\1dev"/' "$MAIN_PY"
}
trap restore_main_py EXIT

# Select application branding icon with PNG preference and ICO fallback
ICON_PNG="$PROJECT_ROOT/resources/icons/fallbyte_icon.png"
ICON_ICO="$PROJECT_ROOT/resources/icons/fallbyte_icon.ico"

if [ -f "$ICON_PNG" ]; then
    ICON_PATH="$ICON_PNG"
elif [ -f "$ICON_ICO" ]; then
    ICON_PATH="$ICON_ICO"
else
    ICON_PATH="$ICON_PNG"
fi

export ICON_SRC="$ICON_PATH"

if [ -z "$TARGET_VERSION" ]; then
    echo -n "==> Enter target release version (e.g., 1.2.1): "
    read -r TARGET_VERSION
fi

if [ -z "$TARGET_VERSION" ]; then
    echo "ERROR: No release version was specified."
    exit 1
fi

export APP_VERSION="$TARGET_VERSION"

echo "=================================================="
echo " Starting FallByte Release Pipeline v${APP_VERSION}"
echo " Selected Icon: ${ICON_SRC}"
echo "=================================================="

# 2. Clean build directory workspace
echo "--> [1/5] Purging previous build workspace..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# 3. Inject target version into main entry point constant
echo "--> [2/5] Injecting APP_VERSION into main.py..."
sed -i -E "s/^(APP_VERSION\s*=\s*\").*/\1${APP_VERSION}\"/" "$MAIN_PY"

# 4. Synchronize version directive in RPM specfile
if [ -f "$SPEC_FILE" ]; then
    echo "--> [3/5] Synchronizing RPM spec metadata..."
    sed -i -E "s/^(Version:\s+).*/\1${APP_VERSION}/" "$SPEC_FILE"
fi

# 5. Compile Python source into isolated directory bundle
echo "--> [4/5] Compiling application binaries with PyInstaller..."

pyinstaller \
    --noconfirm \
    --clean \
    --onedir \
    --windowed \
    --name="FallByte" \
    --icon="$ICON_SRC" \
    --distpath "$PYINSTALLER_DIR/dist" \
    --workpath "$PYINSTALLER_DIR/build" \
    "$MAIN_PY"

# 6. Invoke Linux downstream packaging scripts
echo "--> [5/5] Generating target Linux distribution packages..."

echo " -> Building AppImage..."
"$SCRIPT_DIR/appimage/build_appimage.sh" "$APP_VERSION" "$ICON_SRC"

echo " -> Building Debian package (.deb)..."
"$SCRIPT_DIR/deb/build_deb.sh" "$APP_VERSION" "$ICON_SRC"

echo " -> Building RedHat package (.rpm)..."
"$SCRIPT_DIR/rpm/build_rpm.sh" "$APP_VERSION" "$ICON_SRC"

# Clean up temporary PyInstaller specfile created in packaging/
rm -f "$SCRIPT_DIR/FallByte.spec"

echo "=================================================="
echo " SUCCESS: All Linux distribution packages generated for v${APP_VERSION}"
echo " Artifacts location: $BUILD_DIR"
echo "=================================================="