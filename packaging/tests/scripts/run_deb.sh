#!/usr/bin/env bash
# ==============================================================================
# FallByte Debian Package (.deb) Integration & Upgrade Test Script
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

DEB_FILE=$(find /artifacts -name "*.deb" | head -n 1)

if [ -z "$DEB_FILE" ]; then
    log_error "No .deb package artifact found in /artifacts."
    exit 1
fi

log_info "1. Simulating previous installation (v0.0.1) to test in-place upgrade..."
OLD_DEB_DIR="/tmp/fallbyte_old_deb"
OLD_DEB_FILE="/tmp/fallbyte_0.0.1_amd64.deb"
rm -rf "$OLD_DEB_DIR" "$OLD_DEB_FILE"
dpkg-deb -R "$DEB_FILE" "$OLD_DEB_DIR"
sed -i -E 's/^Version:.*/Version: 0.0.1/' "$OLD_DEB_DIR/DEBIAN/control"
dpkg-deb -b "$OLD_DEB_DIR" "$OLD_DEB_FILE" >/dev/null

dpkg -i "$OLD_DEB_FILE" || { apt-get update && apt-get install -f -y; }

# Create mock user configuration to verify persistence across upgrades
mkdir -p "$HOME/.fallbyte"
echo "theme=dark" > "$HOME/.fallbyte/test_persist.cfg"

log_info "2. Upgrading Debian package to target artifact: $DEB_FILE"
dpkg -i "$DEB_FILE" || { apt-get update && apt-get install -f -y; }

log_info "3. Verifying installed package metadata, AppStream XML, and preserved config"
dpkg -s fallbyte

if [ ! -f "/usr/share/metainfo/fallbyte.metainfo.xml" ]; then
    log_error "AppStream metainfo XML not found in /usr/share/metainfo/."
    exit 1
fi

if [ ! -f "$HOME/.fallbyte/test_persist.cfg" ]; then
    log_error "User configuration in ~/.fallbyte was lost during package upgrade."
    exit 1
fi

BIN_PATH="/usr/bin/fallbyte"
if [ ! -x "$BIN_PATH" ]; then
    log_error "Executable binary not found at $BIN_PATH"
    exit 1
fi

log_info "4. Running binary dependency, CLI, and headless GUI tests"
check_shared_libraries "/usr/lib/fallbyte/FallByte"
run_cli_checks "$BIN_PATH"
run_gui_headless_check "$BIN_PATH"

log_info "5. Uninstalling package"
dpkg -r fallbyte

if [ -f "$BIN_PATH" ]; then
    log_error "Binary still exists after package removal."
    exit 1
fi

rm -rf "$OLD_DEB_DIR" "$OLD_DEB_FILE" "$HOME/.fallbyte"
log_info "Debian package installation, upgrade, and removal verified successfully."