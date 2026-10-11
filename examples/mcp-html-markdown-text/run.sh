#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python -m unittest -v test_contract
python replay.py --verify
