#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
OUTPUT_DIR="${OUTPUT_DIR:-run_output}"
if [[ $# -ne 0 ]]; then
  echo 'Usage: PYTHON_BIN=python3 OUTPUT_DIR=run_output ./run.sh' >&2
  exit 2
fi
mkdir -p "$OUTPUT_DIR"
"$PYTHON_BIN" offline_checks.py --output "$OUTPUT_DIR/offline-checks.json"
"$PYTHON_BIN" quickstart.py --output "$OUTPUT_DIR/quickstart.json"
"$PYTHON_BIN" browser_matrix.py --browser chromium --output "$OUTPUT_DIR/chromium.json"
"$PYTHON_BIN" browser_matrix.py --browser firefox --output "$OUTPUT_DIR/firefox.json"
"$PYTHON_BIN" summarize.py --input-dir "$OUTPUT_DIR" --output "$OUTPUT_DIR/summary.json"
if [[ -f manifest.json ]]; then
  "$PYTHON_BIN" integrity.py
fi
