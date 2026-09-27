#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
NODE_BIN="${NODE_BIN:-node}"
OUTPUT_DIR="${OUTPUT_DIR:-run_output}"
if [[ $# -ne 0 ]]; then echo 'Usage: ./run.sh' >&2; exit 2; fi
mkdir -p "$OUTPUT_DIR"
"$NODE_BIN" test_suite.mjs "$OUTPUT_DIR/test-results.json"
"$NODE_BIN" quickstart.mjs "$OUTPUT_DIR/quickstart.json"
"$NODE_BIN" matrix.mjs "$OUTPUT_DIR/chrome.json"
"$NODE_BIN" summarize.mjs "$OUTPUT_DIR/chrome.json" "$OUTPUT_DIR/comparison.json"
