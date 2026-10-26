#!/usr/bin/env bash
# Runs every snippet of the "Web Scraping with JavaScript" guide and saves its output.
# 08 calls the ScrapingAnt API and runs only when SCRAPINGANT_API_KEY is set.
set -uo pipefail
cd "$(dirname "$0")"
OUT=expected_output; mkdir -p "$OUT"
{ node --version; for p in cheerio jsdom axios playwright puppeteer; do echo "$p $(node -p "require('./node_modules/$p/package.json').version")"; done; } | tee "$OUT/00_versions.txt"
fail=0
for f in cases/*.js; do
  name=$(basename "$f" .js)
  if [[ $name == 08_* && -z "${SCRAPINGANT_API_KEY:-}" ]]; then echo "--- $name skipped (no SCRAPINGANT_API_KEY)"; continue; fi
  echo "--- $name"
  node "$f" 2>&1 | tee "$OUT/$name.txt"; [ "${PIPESTATUS[0]}" = 0 ] || fail=1
done
exit $fail
