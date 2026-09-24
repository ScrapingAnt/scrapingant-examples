#!/usr/bin/env bash
# The request as a buyer would type it: GET /v2/markdown with the default browser mode.
[ -z "${SCRAPINGANT_API_KEY:-}" ] && { echo "skipped: SCRAPINGANT_API_KEY is not set"; exit 0; }
URL="https://scrapingant.github.io/scrapingant-examples/fixtures/markdown-article.html"
curl -sS -D headers.tmp -o body.tmp "https://api.scrapingant.com/v2/markdown?url=${URL}" -H "x-api-key: ${SCRAPINGANT_API_KEY}"
echo "\$ curl 'https://api.scrapingant.com/v2/markdown?url=${URL}' -H 'x-api-key: \$SCRAPINGANT_API_KEY'"
head -1 headers.tmp | tr -d '\r'
grep -i -E "^(content-type|ant-credits-cost|ant-page-status-code):" headers.tmp | tr -d '\r' | sort
echo "--- body, first 400 bytes as returned"
head -c 400 body.tmp; echo
echo "--- body (jq): url, markdown length in characters, first 25 lines of markdown"
jq -r '.url' body.tmp
jq -r '.markdown | length' body.tmp
jq -r '.markdown' body.tmp | head -25
rm -f headers.tmp body.tmp
