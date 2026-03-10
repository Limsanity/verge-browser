#!/usr/bin/env bash
set -euo pipefail

DISPLAY_NUM="${DISPLAY:-:99}"
XVFB_WHD="${XVFB_WHD:-1280x1024x24}"

Xvfb "${DISPLAY_NUM}" -screen 0 "${XVFB_WHD}" -ac +extension RANDR &
sleep 1
DISPLAY="${DISPLAY_NUM}" openbox &
wait -n

