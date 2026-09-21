#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p expected_output
capture() {
  local name="$1"; shift
  { printf '$'; printf ' %q' "$@"; printf '\n'; "$@"; } 2>&1 | tee "expected_output/$name.txt"
}
capture 00_versions python 00_versions.py
capture 01_chrome_headless python chrome_download.py
capture 02_firefox_headless python firefox_download.py
if [[ "${HEADLESS_ONLY:-0}" == "1" ]]; then
  echo 'Headed runs excluded explicitly (HEADLESS_ONLY=1).'
else
  capture 01_chrome_headed python chrome_download.py --headed
  capture 02_firefox_headed python firefox_download.py --headed
fi
capture 03_failures python 03_failures.py
capture 04_http python 04_http.py
capture 05_old_apis python 05_old_apis.py
capture 06_helper_tests python -m unittest -v test_wait
