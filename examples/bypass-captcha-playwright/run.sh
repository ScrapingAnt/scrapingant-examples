#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python}"
# Default checks have no secret or paid-solver dependency. Keep historical outputs intact.
OUTPUT_DIR="${OUTPUT_DIR:-run_output}"
mkdir -p "$OUTPUT_DIR"
case "${1:-}" in
  "") ;;
  --scrapingant) "$PYTHON_BIN" 06_scrapingant.py | tee "$OUTPUT_DIR/06_scrapingant.json"; exit ;;
  *) echo 'Usage: ./run.sh [--scrapingant]' >&2; exit 2 ;;
esac
"$PYTHON_BIN" -m unittest -v test_paid_demo.py test_broad_matrix.py test_summarize_broad.py
"$PYTHON_BIN" 01_test_keys.py | tee "$OUTPUT_DIR/01_test_keys.json"
for script in 04_2captcha 05_anticaptcha 07_capsolver; do
  "$PYTHON_BIN" "$script.py" | tee "$OUTPUT_DIR/$script.json"
done
