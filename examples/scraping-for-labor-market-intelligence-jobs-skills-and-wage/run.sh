#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
if [[ "$("$PYTHON_BIN" -c 'import platform; print(platform.python_version())')" != "3.12.11" ]]; then
  echo 'Use CPython 3.12.11 (.python-version); set PYTHON_BIN to its executable.' >&2
  exit 1
fi
export PYTHONDONTWRITEBYTECODE=1
if [[ "${1:-}" == "--check" ]]; then
  scratch_dir="$(mktemp -d)"
  trap 'rm -rf "$scratch_dir"' EXIT
  "$PYTHON_BIN" -m unittest -v test_collector
  "$PYTHON_BIN" -m unittest -v test_greenhouse_single_post
  "$PYTHON_BIN" demo.py --output-dir "$scratch_dir"
  "$PYTHON_BIN" verify_captures.py --fresh-dir "$scratch_dir"
elif [[ $# -eq 0 ]]; then
  mkdir -p expected_output
  "$PYTHON_BIN" -m unittest -v test_collector 2>&1 | tee expected_output/tests.txt
  "$PYTHON_BIN" -m unittest -v test_greenhouse_single_post 2>&1 | tee expected_output/single-post-tests.txt
  "$PYTHON_BIN" demo.py
  "$PYTHON_BIN" verify_captures.py
else
  echo 'Usage: ./run.sh [--check]' >&2
  exit 1
fi
