#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p expected_output
{ python --version; uv pip freeze --python "$(command -v python)" 2>/dev/null | grep -iE '^(requests|pysocks|proxy-py|proxy\.py|pproxy|urllib3)=='; } | tee expected_output/00_versions.txt
python lab.py "$@" 2>&1 | tee expected_output/run.txt
