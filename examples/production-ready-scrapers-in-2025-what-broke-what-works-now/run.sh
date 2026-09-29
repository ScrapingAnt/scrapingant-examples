#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python3}"
mkdir -p expected_output
"$PYTHON" -m unittest -v test_policy 2>&1 | tee expected_output/policy_tests.txt
"$PYTHON" run_matrix.py | tee expected_output/run.txt
