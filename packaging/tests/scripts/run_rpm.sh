#!/usr/bin/env bash
# ==============================================================================
# FallByte RPM Package (.rpm) Integration & Upgrade Test Script
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

log_info "1. Locating RPM package in artifacts..."
RPM_PATH=$(find /artifacts -type f -name "*.rpm" 2>/dev/null | head -n 1)

if [ -z "$RPM_PATH" ]; then
    log_error "No .rpm package artifact found in /artifacts."
    exit 1
fi

log_info "Found RPM: $RPM_PATH"
log_info "2. Installing RPM package..."
dnf install -y "$RPM_PATH"

# Simulate user config and test idempotent reinstall/upgrade flow
mkdir -p "$HOME/.fallbyte"
echo "theme=dark" > "$HOME/.fallbyte/test_persist.cfg"

log_info "3. Testing package reinstall/upgrade idempotency..."
dnf reinstall -y "$RPM_PATH"

if [ ! -f "$HOME/.fallbyte/test_persist.cfg" ]; then
    log_error "User configuration in ~/.fallbyte was lost during RPM upgrade/reinstall."
    exit 1
fi

log_info "4. Verifying RPM installation metadata and AppStream XML..."
rpm -qi fallbyte

if [ ! -f "/usr/share/metainfo/fallbyte.metainfo.xml" ]; then
    log_error "AppStream metainfo XML not found in /usr/share/metainfo/."
    exit 1
fi

BIN_PATH="/usr/bin/fallbyte"
if [ ! -x "$BIN_PATH" ]; then
    log_error "Executable binary not found at $BIN_PATH"
    exit 1
fi

log_info "5. Running binary dependency, CLI, and headless GUI tests..."
check_shared_libraries "/usr/lib64/fallbyte/FallByte"
run_cli_checks "$BIN_PATH"
run_gui_headless_check "$BIN_PATH"

log_info "6. Uninstalling RPM package..."
dnf remove -y fallbyte

if [ -f "$BIN_PATH" ]; then
    log_error "Binary still exists after RPM removal."
    exit 1
fi

rm -rf "$HOME/.fallbyte"
log_info "RPM package verification completed successfully."