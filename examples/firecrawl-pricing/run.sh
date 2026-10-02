#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m unittest -v test_offline.py
python3 score.py | tee expected_output/replay.txt
python3 budget.py | tee expected_output/budget.json
