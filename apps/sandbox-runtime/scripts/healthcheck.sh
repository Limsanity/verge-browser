#!/usr/bin/env bash
set -euo pipefail

curl --fail --silent http://127.0.0.1:9222/json/version >/dev/null

