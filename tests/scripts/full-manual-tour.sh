#!/usr/bin/env bash
# Purpose: Run the most useful human smoke flow end to end: create a sandbox, save screenshots, validate files and shell, and print a VNC URL.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

"$SCRIPT_DIR/create-sandbox.sh"
echo
"$SCRIPT_DIR/browser-smoke.sh"
echo
"$SCRIPT_DIR/file-shell-smoke.sh"
echo
"$SCRIPT_DIR/get-vnc-url.sh"
