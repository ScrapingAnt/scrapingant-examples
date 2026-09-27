#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python}"
OUTPUT_DIR="${OUTPUT_DIR:-run_output}"
mkdir -p "$OUTPUT_DIR"
# A configured API key never enables a paid request implicitly.
if [[ "${1:-}" == "--scrapingant" ]]; then
  "$PYTHON_BIN" scrapingant_cookies.py --live --output "$OUTPUT_DIR/scrapingant.json"
  exit
fi
if [[ -n "${1:-}" && "${1:-}" != "--all-browsers" ]]; then
  echo 'Usage: ./run.sh [--all-browsers|--scrapingant]' >&2; exit 2
fi
"$PYTHON_BIN" -m unittest -v test_cookie_state.py test_scrapingant_cookies.py test_browser_matrix.py
"$PYTHON_BIN" browser_matrix.py --browser chrome --rounds 3 --output "$OUTPUT_DIR/chrome.json"
if [[ "${1:-}" == "--all-browsers" ]]; then
  "$PYTHON_BIN" browser_matrix.py --browser firefox --rounds 3 --output "$OUTPUT_DIR/firefox.json"
fi
