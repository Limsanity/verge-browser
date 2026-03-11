#!/usr/bin/env bash
# Purpose: Reuse a sandbox, fetch browser metadata, and save both window and page screenshots for manual inspection.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_common.sh"

require_sandbox_id

run_dir="$ARTIFACTS_DIR/browser-$(timestamp)"
mkdir -p "$run_dir"

api_json GET "$BASE_URL/sandboxes/$SANDBOX_ID/browser/info" | tee "$run_dir/browser-info.json" >/dev/null
api_json GET "$BASE_URL/sandboxes/$SANDBOX_ID/browser/viewport" | tee "$run_dir/viewport.json" >/dev/null
api_json GET "$BASE_URL/sandboxes/$SANDBOX_ID/browser/cdp/info" | tee "$run_dir/cdp-info.json" >/dev/null
api_json GET "$BASE_URL/sandboxes/$SANDBOX_ID/browser/screenshot?type=window" > "$run_dir/window.json"
api_json GET "$BASE_URL/sandboxes/$SANDBOX_ID/browser/screenshot?type=page" > "$run_dir/page.json"

python3 - "$run_dir/window.json" "$run_dir/window.png" <<'PY'
import base64, json, pathlib, sys
src = pathlib.Path(sys.argv[1])
dst = pathlib.Path(sys.argv[2])
dst.write_bytes(base64.b64decode(json.loads(src.read_text())["data_base64"]))
PY

python3 - "$run_dir/page.json" "$run_dir/page.png" <<'PY'
import base64, json, pathlib, sys
src = pathlib.Path(sys.argv[1])
dst = pathlib.Path(sys.argv[2])
dst.write_bytes(base64.b64decode(json.loads(src.read_text())["data_base64"]))
PY

echo "Artifacts saved to $run_dir"
echo "Window screenshot: $run_dir/window.png"
echo "Page screenshot:   $run_dir/page.png"
echo "Browser info:      $run_dir/browser-info.json"
