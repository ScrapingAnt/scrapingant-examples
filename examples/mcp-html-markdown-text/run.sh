#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python -m unittest -v test_contract test_live test_model test_summary
python replay.py --verify
