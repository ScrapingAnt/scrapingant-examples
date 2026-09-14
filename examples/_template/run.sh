#!/usr/bin/env bash
# Runs every approach in this example and captures output. Exit non-zero on any failure.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p expected_output
status=0
for script in *.py; do
  name="${script%.py}"
  echo "== $name"
  if python "$script" | tee "expected_output/$name.txt"; then :; else echo "FAILED: $name"; status=1; fi
done
exit $status
