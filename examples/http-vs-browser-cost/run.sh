#!/usr/bin/env bash
set -euo pipefail
python -m unittest discover -v -p 'test_*.py'
python runner.py --out run_output/local
python verify_capture.py run_output/local/report.json
