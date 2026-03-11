#!/usr/bin/env bash
# Purpose: Verify shared workspace behavior by writing a file, listing it, reading it back, and reading it from shell exec.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_common.sh"

require_sandbox_id

run_dir="$ARTIFACTS_DIR/file-shell-$(timestamp)"
mkdir -p "$run_dir"
content="hello verge from $(timestamp)"

api_json POST "$BASE_URL/sandboxes/$SANDBOX_ID/files/write" \
  -H 'Content-Type: application/json' \
  -d "{\"path\":\"/workspace/manual-notes.txt\",\"content\":\"$content\",\"overwrite\":true}" \
  | tee "$run_dir/write.json" >/dev/null

api_json GET "$BASE_URL/sandboxes/$SANDBOX_ID/files/list?path=/workspace" | tee "$run_dir/list.json" >/dev/null
api_json GET "$BASE_URL/sandboxes/$SANDBOX_ID/files/read?path=/workspace/manual-notes.txt" | tee "$run_dir/read.json" >/dev/null
api_json POST "$BASE_URL/sandboxes/$SANDBOX_ID/shell/exec" \
  -H 'Content-Type: application/json' \
  -d '{"argv":["bash","-lc","pwd && ls -la && cat manual-notes.txt"],"cwd":"/workspace","timeout_sec":30}' \
  | tee "$run_dir/shell-exec.json" >/dev/null

echo "Artifacts saved to $run_dir"
echo "Readback file:  $run_dir/read.json"
echo "Shell output:   $run_dir/shell-exec.json"
