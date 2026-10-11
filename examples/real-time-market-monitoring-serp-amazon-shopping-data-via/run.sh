#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python3}"
mkdir -p expected_output
"$PYTHON" run_tests.py | tee expected_output/tests.json
"$PYTHON" snapshot.py fixtures/baseline.html | tee expected_output/baseline.json
"$PYTHON" snapshot.py fixtures/changed.html | tee expected_output/changed.json
"$PYTHON" snapshot.py fixtures/truncated.html | tee expected_output/truncated.json
"$PYTHON" snapshot.py fixtures/baseline.html fixtures/changed.html | tee expected_output/changed-diff.json
"$PYTHON" snapshot.py fixtures/baseline.html fixtures/truncated.html | tee expected_output/truncated-diff.json
"$PYTHON" naive.py | tee expected_output/naive.json
"$PYTHON" budget.py | tee expected_output/budget.json
"$PYTHON" verify_captures.py | tee expected_output/verification.json
"$PYTHON" environment.py | tee expected_output/environment.json
