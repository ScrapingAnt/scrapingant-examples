#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python}"
OUTPUT_DIR="${OUTPUT_DIR:-expected_output}"
mkdir -p "$OUTPUT_DIR"
case "${1:-}" in
  ""|--all) ;;
  *) echo 'Usage: ./run.sh [--all]' >&2; exit 2 ;;
esac
for script in 01_playwright 02_patchright 03_python_stealth; do
  "$PYTHON_BIN" "$script.py" | tee "$OUTPUT_DIR/$script.txt"
done
if [[ "${1:-}" == --all ]]; then
  : "${CAMOUFOX_PYTHON:?Set CAMOUFOX_PYTHON to the separate Camoufox environment interpreter}"
  node 04_extra_stealth.cjs | tee "$OUTPUT_DIR/04_extra_stealth.txt"
  node 05_rebrowser.cjs | tee "$OUTPUT_DIR/05_rebrowser.txt"
  "$CAMOUFOX_PYTHON" 06_firefox.py | tee "$OUTPUT_DIR/06_firefox.txt"
  "$CAMOUFOX_PYTHON" 07_camoufox.py | tee "$OUTPUT_DIR/07_camoufox.txt"
fi
