#!/usr/bin/env bash
set -e

source "$(dirname "$0")/common.sh"

echo "[INFO] 1. Locating RPM package in artifacts..."
RPM_PATH=$(find /artifacts -type f -name "*.rpm" 2>/dev/null | head -n 1)

if [ -z "$RPM_PATH" ]; then
    echo "[ERROR] No .rpm package artifact found in /artifacts."
    exit 1
fi

echo "[INFO] Found RPM: $RPM_PATH"
echo "[INFO] Installing RPM package..."
dnf install -y "$RPM_PATH"

echo "[INFO] Verifying RPM installation metadata..."
rpm -qi fallbyte

echo "[INFO] Running CLI sanity checks..."
/usr/bin/fallbyte --version
/usr/bin/fallbyte --smoke-test

echo "[INFO] Testing GUI startup under xvfb-run..."
xvfb-run -a /usr/bin/fallbyte --help >/dev/null 2>&1 || true

echo "[INFO] Uninstalling RPM package..."
dnf remove -y fallbyte

echo "[INFO] RPM package verification completed successfully."