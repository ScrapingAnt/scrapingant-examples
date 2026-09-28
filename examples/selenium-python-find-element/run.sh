#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python}"
OUTPUT_DIR="${OUTPUT_DIR:-run_output}"
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != '--all-browsers' ) ]]; then
  echo 'Usage: ./run.sh [--all-browsers]' >&2
  exit 2
fi
mkdir -p "$OUTPUT_DIR"
"$PYTHON_BIN" -m unittest -v test_packet.py 2>&1 | tee "$OUTPUT_DIR/tests.txt"
"$PYTHON_BIN" -m unittest -v test_browser.py 2>&1 | tee "$OUTPUT_DIR/tests-browser.txt"
"$PYTHON_BIN" quickstart.py | tee "$OUTPUT_DIR/quickstart.json"
"$PYTHON_BIN" browser_matrix.py --browser chrome --output "$OUTPUT_DIR/chrome.json"
captures=("$OUTPUT_DIR/chrome.json")
if [[ "${1:-}" == '--all-browsers' ]]; then
  "$PYTHON_BIN" browser_matrix.py --browser firefox --output "$OUTPUT_DIR/firefox.json"
  captures+=("$OUTPUT_DIR/firefox.json")
fi
"$PYTHON_BIN" summarize.py "${captures[@]}" --output "$OUTPUT_DIR/summary.json"
