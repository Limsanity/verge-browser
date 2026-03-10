#!/usr/bin/env bash
set -euo pipefail

DISPLAY_NUM="${DISPLAY:-:99}"
VNC_SERVER_PORT="${VNC_SERVER_PORT:-5900}"
WEBSOCKET_PROXY_PORT="${WEBSOCKET_PROXY_PORT:-6080}"

x11vnc -display "${DISPLAY_NUM}" -forever -shared -rfbport "${VNC_SERVER_PORT}" -nopw -localhost -xkb &
exec websockify --web /opt/novnc "${WEBSOCKET_PROXY_PORT}" "localhost:${VNC_SERVER_PORT}"

