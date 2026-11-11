#!/usr/bin/env bash
# ==============================================================================
# FallByte Debian Package (.deb) Integration Test Script
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

DEB_FILE=$(find /artifacts -name "*.deb" | head -n 1)

if [ -z "$DEB_FILE" ]; then
    log_error "No .deb package artifact found in /artifacts."
    exit 1
fi

log_info "1. Installing Debian package: $DEB_FILE"
dpkg -i "$DEB_FILE" || apt-get install -f -y

log_info "2. Verifying installed package metadata and files"
dpkg -s fallbyte

BIN_PATH="/usr/bin/fallbyte"
if [ ! -x "$BIN_PATH" ]; then
    log_error "Executable binary not found at $BIN_PATH"
    exit 1
fi

log_info "3. Running binary dependency and CLI tests"
check_shared_libraries "/usr/lib/fallbyte/FallByte"
run_cli_checks "$BIN_PATH"
run_gui_headless_check "$BIN_PATH"

log_info "4. Uninstalling package"
dpkg -r fallbyte

if [ -f "$BIN_PATH" ]; then
    log_error "Binary still exists after package removal."
    exit 1
fi

log_info "Debian package verification completed successfully."