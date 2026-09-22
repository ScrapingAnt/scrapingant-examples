#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p expected_output
python lab.py test 2>&1 | tee expected_output/run.txt
