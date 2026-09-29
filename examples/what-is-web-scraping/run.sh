#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python3}"
mkdir -p expected_output
"$PYTHON" verify.py | tee expected_output/verification.txt
