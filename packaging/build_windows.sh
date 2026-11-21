#!/usr/bin/env bash
# ==============================================================================
# FallByte Windows Release Packaging Orchestrator
# ==============================================================================
# Generates the portable .zip and the Inno Setup installer directly in build/,
# alongside existing packages in build/. Intermediate files are removed on exit.
#
# Usage:
#   ./build_windows.sh [OPTIONS] [VERSION]
#
# Options:
#   --version=<version>, -v <version>   Specify the target release version (e.g., 2.0.0).
#   --help, -h                          Show this help message and exit.
#
# Examples:
#   ./build_windows.sh --version=2.0.0
#   ./build_windows.sh -v 2.0.0
#   ./build_windows.sh 2.0.0
#   ./build_windows.sh                  (Interactive prompt)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

BUILD_DIR="$PROJECT_ROOT/build"
WORK_DIR="$BUILD_DIR/.windows_work"
DIST_DIR="$WORK_DIR/dist/FallByte"
MAIN_PY="$PROJECT_ROOT/main.py"
NOTICES_SRC="$PROJECT_ROOT/THIRD_PARTY_NOTICES.md"

show_help() {
    cat <<EOF
FallByte Windows Release Packaging Orchestrator

Usage:
  $(basename "$0") [OPTIONS] [VERSION]

Options:
  --version=<version>, -v <version>   Specify the target release version (e.g., 2.0.0).
  --help, -h                          Show this help message and exit.

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
        -*)
            echo "ERROR: Unknown option '$1'."
            echo ""
            show_help
            exit 1
            ;;
        *)
            if [[ -n "$TARGET_VERSION" ]]; then
                echo "ERROR: Unexpected extra argument '$1'."
                exit 1
            fi
            TARGET_VERSION="$1"
            shift
            ;;
    esac
done

if [ -z "$TARGET_VERSION" ]; then
    echo -n "==> Enter target release version (e.g., 2.0.0): "
    read -r TARGET_VERSION
fi

if [ -z "$TARGET_VERSION" ]; then
    echo "ERROR: No release version was specified."
    exit 1
fi

# Validate Semantic Versioning format (e.g., 2.0.0 or 2.0.0-rc1)
if [[ ! "$TARGET_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
    echo "ERROR: Invalid version format '$TARGET_VERSION'. Expected SemVer (e.g., 2.0.0)."
    exit 1
fi

# Convert a path to native Windows form (no-op outside Git Bash/MSYS)
win_path() {
    cygpath -w "$1" 2>/dev/null || echo "$1"
}

# Ensure PyInstaller executable is present in PATH
if ! command -v pyinstaller &> /dev/null; then
    echo "ERROR: 'pyinstaller' executable not found in current PATH."
    echo "HINT: Please activate your active Python environment (e.g., 'conda activate FallByteVenv')."
    exit 1
fi

# Ensure Python is available to create the zip archive
PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON_BIN" ]; then
    echo "ERROR: Python not found in PATH (needed to create the zip archive)."
    exit 1
fi

# Locate the Inno Setup compiler up front so we fail before the long build
ISCC_CMD="$(command -v iscc || command -v ISCC.exe || true)"
if [ -z "$ISCC_CMD" ]; then
    INNO_CANDIDATES=(
        "/c/Program Files (x86)/Inno Setup 6/ISCC.exe"
        "/c/Program Files/Inno Setup 6/ISCC.exe"
    )
    if [ -n "$LOCALAPPDATA" ]; then
        INNO_CANDIDATES+=("$(cygpath -u "$LOCALAPPDATA" 2>/dev/null)/Programs/Inno Setup 6/ISCC.exe")
    fi
    for candidate in "${INNO_CANDIDATES[@]}"; do
        if [ -f "$candidate" ]; then
            ISCC_CMD="$candidate"
            break
        fi
    done
fi

if [ -z "$ISCC_CMD" ]; then
    echo "ERROR: Inno Setup compiler ('ISCC.exe') not found."
    echo "HINT: Install Inno Setup 6 (https://jrsoftware.org/isdl.php) or add it to PATH."
    exit 1
fi

# Cleanup handler: restore main.py to "dev" and remove temporary workspace
restore_and_cleanup() {
    echo "--> Restoring APP_VERSION in main.py back to 'dev'..."
    sed -i -E 's/^(APP_VERSION\s*=\s*").*/\1dev"/' "$MAIN_PY"
    rm -rf "$WORK_DIR"
}
trap restore_and_cleanup EXIT

# Select application branding icon with ICO preference and PNG fallback
ICON_ICO="$PROJECT_ROOT/resources/icons/fallbyte_icon.ico"
ICON_PNG="$PROJECT_ROOT/resources/icons/fallbyte_icon.png"

if [ -f "$ICON_ICO" ]; then
    ICON_PATH="$ICON_ICO"
elif [ -f "$ICON_PNG" ]; then
    ICON_PATH="$ICON_PNG"
else
    ICON_PATH="$ICON_ICO"
fi

export ICON_SRC="$ICON_PATH"
export APP_VERSION="$TARGET_VERSION"

FINAL_ZIP="$BUILD_DIR/fallbyte_${APP_VERSION}_windows_x64.zip"
FINAL_INSTALLER="$BUILD_DIR/fallbyte_${APP_VERSION}_x64_installer.exe"

echo "=================================================="
echo " Starting FallByte Windows Pipeline v${APP_VERSION}"
echo " Selected Icon: ${ICON_SRC}"
echo "=================================================="

# 2. Prepare workspace (other artifacts already in build/ are left untouched)
echo "--> [1/5] Preparing Windows build workspace..."
rm -rf "$WORK_DIR"
rm -f "$FINAL_ZIP" "$FINAL_INSTALLER"
mkdir -p "$WORK_DIR"

# 3. Inject target version into main entry point constant
echo "--> [2/5] Injecting APP_VERSION into main.py..."
sed -i -E "s/^(APP_VERSION\s*=\s*\").*/\1${APP_VERSION}\"/" "$MAIN_PY"

# 4. Compile Python source into isolated directory bundle
echo "--> [3/5] Compiling application binaries with PyInstaller..."

pyinstaller \
    --noconfirm \
    --clean \
    --onedir \
    --windowed \
    --name="FallByte" \
    --icon="$(win_path "$ICON_SRC")" \
    --add-data "$(win_path "$PROJECT_ROOT/resources");resources" \
    --collect-all flet \
    --collect-all pillow_heif \
    --distpath "$(win_path "$WORK_DIR/dist")" \
    --workpath "$(win_path "$WORK_DIR/build")" \
    --specpath "$(win_path "$WORK_DIR")" \
    "$(win_path "$MAIN_PY")"

# Strip non-Windows binaries from bundled resources if present
rm -rf "$DIST_DIR/_internal/resources/bin/linux"* \
       "$DIST_DIR/_internal/resources/bin/darwin"* \
       "$DIST_DIR/_internal/resources/bin/mac"*

if [ -f "$NOTICES_SRC" ]; then
    cp "$NOTICES_SRC" "$DIST_DIR/"
fi

# 5. Portable zip (forward-slash entries, top-level FallByte/ folder)
echo "--> [4/5] Packaging portable zip archive..."
(
    cd "$WORK_DIR/dist" && "$PYTHON_BIN" -m zipfile -c "$(win_path "$FINAL_ZIP")" FallByte
)

# 6. Inno Setup installer
echo "--> [5/5] Compiling Inno Setup installer..."

ISS_FILE="$WORK_DIR/fallbyte.iss"

cat <<'EOF' > "$ISS_FILE"
#ifndef AppVersion
  #define AppVersion "dev"
#endif

[Setup]
AppId={{A8B52839-4B52-4C13-9E11-F2849182312A}
AppName=FallByte
AppVersion={#AppVersion}
AppPublisher=Bruno Henrique (brunothinker)
AppPublisherURL=https://github.com/brunothinker/fallbyte
DefaultDirName={autopf}\FallByte
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=fallbyte_{#AppVersion}_x64_installer
#ifdef IconFile
SetupIconFile={#IconFile}
#endif
UninstallDisplayIcon={app}\FallByte.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\FallByte"; Filename: "{app}\FallByte.exe"
Name: "{autodesktop}\FallByte"; Filename: "{app}\FallByte.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\FallByte.exe"; Description: "{cm:LaunchProgram,FallByte}"; Flags: nowait postinstall skipifsilent
EOF

ISCC_ARGS=(
    "/DAppVersion=${APP_VERSION}"
    "/DSourceDir=$(win_path "$DIST_DIR")"
    "/DOutputDir=$(win_path "$BUILD_DIR")"
)

# SetupIconFile requires an .ico; fall back to the default Inno icon otherwise
if [[ "${ICON_SRC,,}" == *.ico && -f "$ICON_SRC" ]]; then
    ISCC_ARGS+=("/DIconFile=$(win_path "$ICON_SRC")")
else
    echo "WARNING: No .ico icon found; installer will use the default Inno Setup icon."
fi

# MSYS2_ARG_CONV_EXCL keeps Git Bash from rewriting the /D switches as paths
MSYS2_ARG_CONV_EXCL="*" "$ISCC_CMD" "${ISCC_ARGS[@]}" "$(win_path "$ISS_FILE")" > /dev/null

if [ ! -f "$FINAL_INSTALLER" ]; then
    echo "ERROR: Installer was not generated at $FINAL_INSTALLER"
    exit 1
fi

echo "=================================================="
echo " SUCCESS: Windows packages generated for v${APP_VERSION}"
echo "   -> $FINAL_ZIP"
echo "   -> $FINAL_INSTALLER"
echo " Artifacts location: $BUILD_DIR"
echo "=================================================="