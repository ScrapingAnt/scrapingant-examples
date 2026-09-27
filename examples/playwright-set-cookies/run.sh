#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python}"
OUTPUT_DIR="${OUTPUT_DIR:-run_output}"
if [[ -n "${1:-}" && "${1:-}" != "--all-browsers" ]]; then
  echo 'Usage: ./run.sh [--all-browsers]' >&2
  exit 2
fi
mkdir -p "$OUTPUT_DIR"
"$PYTHON_BIN" offline_checks.py --output "$OUTPUT_DIR/offline-checks.json"
BROWSERS=(chromium)
"$PYTHON_BIN" quickstart.py --output "$OUTPUT_DIR/quickstart.json"
"$PYTHON_BIN" browser_matrix.py --browser chromium --rounds 3 --output "$OUTPUT_DIR/chromium.json"
if [[ "${1:-}" == '--all-browsers' ]]; then
  BROWSERS+=(firefox)
  "$PYTHON_BIN" browser_matrix.py --browser firefox --rounds 3 --output "$OUTPUT_DIR/firefox.json"
fi
"$PYTHON_BIN" summarize.py --input-dir "$OUTPUT_DIR" --browsers "${BROWSERS[@]}" --output "$OUTPUT_DIR/comparison.json"
