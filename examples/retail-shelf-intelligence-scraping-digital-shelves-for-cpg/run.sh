#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ "$#" -ne 0 ]; then
  echo "run.sh is the offline replay only; use collector.py for explicit optional commands" >&2
  exit 2
fi
PYTHON="${PYTHON:-python3}"
"$PYTHON" -c 'import sys; assert sys.implementation.name == "cpython" and sys.version_info[:3] == (3,12,11), "Use CPython 3.12.11 (PYTHON=/path/to/python)"'
mkdir -p expected_output
"$PYTHON" offline_tests.py 2>&1 | tee expected_output/tests.txt
"$PYTHON" mutation_check.py | tee expected_output/negative-controls.txt
"$PYTHON" demo.py | tee expected_output/summary.txt
