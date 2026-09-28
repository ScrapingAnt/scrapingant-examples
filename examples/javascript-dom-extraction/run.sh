#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python -m unittest -v test_protocol.py test_state.py test_summary.py
node --test test-protocol.mjs
python run_local.py "$@"
