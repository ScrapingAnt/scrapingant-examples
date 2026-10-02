#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 -m unittest discover -s . -p "test_*.py" -v
python3 capture_examples.py --check
python3 make_visuals.py --check
