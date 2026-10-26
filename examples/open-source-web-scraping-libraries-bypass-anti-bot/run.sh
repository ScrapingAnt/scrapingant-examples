#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
OUT=expected_output; mkdir -p "$OUT"
{ node --version; echo "playwright $(node -p "require('./node_modules/playwright/package.json').version")"; } | tee "$OUT/00_versions.txt"
./status.sh | tee "$OUT/status.txt"
fail=0
echo "--- 01_playwright_headless"; node cases/01_playwright_headless.js | tee "$OUT/01_playwright_headless.txt"; [ "${PIPESTATUS[0]}" = 0 ] || fail=1
if [ -n "${SCRAPINGANT_API_KEY:-}" ]; then echo "--- 02_scrapingant_api"; node cases/02_scrapingant_api.js | tee "$OUT/02_scrapingant_api.txt"; [ "${PIPESTATUS[0]}" = 0 ] || fail=1; fi
exit $fail
