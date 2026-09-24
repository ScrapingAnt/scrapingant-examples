#!/usr/bin/env bash
# POST is forwarded to the target: the fixture host (GitHub Pages) answers 405 to POST; record what the API returns.
[ -z "${SCRAPINGANT_API_KEY:-}" ] && { echo "skipped: SCRAPINGANT_API_KEY is not set"; exit 0; }
URL="https://scrapingant.github.io/scrapingant-examples/fixtures/markdown-article.html"
curl -sS -X POST -D headers.tmp -o body.tmp "https://api.scrapingant.com/v2/markdown?url=${URL}" -H "x-api-key: ${SCRAPINGANT_API_KEY}" -H "Ant-Content-Type: application/json" -d '{"probe": true}'
echo "\$ curl -X POST 'https://api.scrapingant.com/v2/markdown?url=${URL}' -H 'x-api-key: ...' -H 'Ant-Content-Type: application/json' -d '{\"probe\": true}'"
head -1 headers.tmp | tr -d '\r'
grep -i -E "^(ant-credits-cost|ant-page-status-code):" headers.tmp | tr -d '\r' | sort
echo "--- body (first 200 characters)"; head -c 200 body.tmp; echo
rm -f headers.tmp body.tmp
