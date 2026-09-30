#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python -B -m unittest discover -v
python -B replay.py --capture expected_output/anthropic-2026-09-30
