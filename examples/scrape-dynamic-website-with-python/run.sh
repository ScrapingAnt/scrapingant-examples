#!/usr/bin/env bash
# Runs every approach and captures output into expected_output/. Exit non-zero on any failure.
# 04_scrapingant_api.py needs SCRAPINGANT_API_KEY; it is skipped (not failed) when unset.
set -uo pipefail
cd "$(dirname "$0")"
mkdir -p expected_output
status=0
for script in 0*.py; do
  name="${script%.py}"
  if [ "$name" = "04_scrapingant_api" ] && [ -z "${SCRAPINGANT_API_KEY:-}" ]; then
    echo "== $name: SKIPPED (SCRAPINGANT_API_KEY not set)"; continue
  fi
  echo "== $name"
  if python "$script" 2>&1 | tee "expected_output/$name.txt"; then :; fi
  if [ "${PIPESTATUS[0]}" -ne 0 ]; then echo "FAILED: $name"; status=1; fi
done
exit $status
