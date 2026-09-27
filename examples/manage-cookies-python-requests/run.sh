#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ $# -gt 0 ]]; then
  echo 'Usage: ./run.sh' >&2
  exit 2
fi
PYTHON_BIN="${PYTHON_BIN:-python}"
# Captures are intentionally immutable; reruns only write ignored output.
mkdir -p run_output
"$PYTHON_BIN" run_checks.py --output run_output/checks.json
"$PYTHON_BIN" quickstart.py > run_output/quickstart.json
"$PYTHON_BIN" requests_matrix.py --rounds 3 --output run_output/requests.json
"$PYTHON_BIN" summarize.py --input run_output/requests.json > run_output/comparison.json
