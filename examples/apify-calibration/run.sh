#!/bin/sh
set -eu
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1
APIFY_CALIBRATION_PYTHON="${PYTHON:-python3}"
"$APIFY_CALIBRATION_PYTHON" -m unittest -v test_calibration
"$APIFY_CALIBRATION_PYTHON" calibration.py --plan
