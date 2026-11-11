#!/usr/bin/env bash
# ==============================================================================
# FallByte Package Test Suite - Common Utilities
# ==============================================================================

set -e

COLOR_GREEN="\033[0;32m"
COLOR_RED="\033[0;31m"
COLOR_RESET="\033[0m"

log_info() {
    echo -e "${COLOR_GREEN}[INFO] $1${COLOR_RESET}"
}

log_error() {
    echo -e "${COLOR_RED}[ERROR] $1${COLOR_RESET}" >&2
}

run_cli_checks() {
    local bin_path="$1"
    
    log_info "Testing CLI flag: --version"
    "$bin_path" --version || {
        log_error "Failed executing '--version' check."
        exit 1
    }

    log_info "Testing CLI flag: --smoke-test"
    "$bin_path" --smoke-test || {
        log_error "Failed executing '--smoke-test' check."
        exit 1
    }
}

run_gui_headless_check() {
    local bin_path="$1"
    log_info "Testing GUI startup under xvfb-run..."
    
    if command -v xvfb-run &>/dev/null; then
        timeout 5s xvfb-run --auto-servernum "$bin_path" || local ret=$?
        # Exit code 124 indicates timeout reached (application launched and stayed alive)
        if [ "${ret:-0}" -eq 124 ] || [ "${ret:-0}" -eq 0 ]; then
            log_info "GUI headless test passed successfully."
        else
            log_error "GUI startup failed with exit code ${ret:-0}."
            exit 1
        fi
    else
        log_error "'xvfb-run' command not found. Skipping GUI headless check."
    fi
}

check_shared_libraries() {
    local bin_path="$1"
    log_info "Inspecting unresolved shared library linkages (ldd)..."
    
    if command -v ldd &>/dev/null; then
        local missing_libs
        missing_libs=$(ldd "$bin_path" 2>&1 | grep "not found" || true)
        if [ -n "$missing_libs" ]; then
            log_error "Unresolved shared library dependencies detected:\n$missing_libs"
            exit 1
        fi
        log_info "No missing shared libraries detected by ldd."
    fi
}