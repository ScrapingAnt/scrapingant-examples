#!/usr/bin/env bash
# Every request and measurement behind https://scrapingant.com/llm-ready-data-extraction. Needs SCRAPINGANT_API_KEY; without it every script prints "skipped".
set -uo pipefail
export LC_ALL=C LANG=C
cd "$(dirname "$0")"; mkdir -p expected_output generated; rm -f expected_output/[0-9]*.txt generated/*; status=0
{ echo "python: $(python --version 2>&1)"; echo "node: $(node --version)"; echo "curl: $(curl --version | head -1 | cut -d' ' -f1-2)"; python -c "
from importlib.metadata import version
for p in ('requests','tiktoken','html2text','beautifulsoup4'): print(p, version(p))"; echo "fixture: $(curl -s -o /dev/null -w '%{http_code}' https://scrapingant.github.io/scrapingant-examples/fixtures/markdown-article.html)"; } > expected_output/00_versions.txt
run() { name="$1"; shift; echo "== $name"; { echo "\$ $*"; "$@" 2>&1; echo "exit=$?"; } > "expected_output/$name.txt"; }
run 01_request_curl bash 01_request_curl.sh
run 02_request_python python 02_request_python.py
run 03_request_node node --experimental-strip-types --no-warnings 03_request_node.ts
run 04_tokens python 04_tokens.py
run 05_keep_remove python 05_keep_remove.py
run 06_browser_false python 06_browser_false.py
run 07_latency python 07_latency.py
run 08_errors python 08_errors.py
run 09_js_snippet_cleanup python 09_js_snippet_cleanup.py
run 10_methods bash 10_methods.sh
for f in expected_output/[0-9]*.txt; do echo "=== $f"; cat "$f"; done
g() { grep -qF -- "$2" "expected_output/$1"*.txt || { echo "FAILED: $1 missing '$2'"; status=1; }; }
for n in 01 02 03 04 05 06 07 08 09 10; do g $n "exit=0"; done
if [ -n "${SCRAPINGANT_API_KEY:-}" ]; then
  g 01 "HTTP/2 200"; g 01 "ant-credits-cost: 10"; g 02 "Ant-credits-cost: 10"; g 02 "keys: ['markdown', 'url']"; g 03 "status: 200"
  g 04 "fixture"; g 05 "ok  script body absent"; g 05 "ok  navigation link text present"; g 05 "ok  table as pipe rows"
  g 06 "cost 1"; g 07 "median"; g 08 "status 403"; g 09 "ok  navigation gone"; g 09 "ok  article kept"
  grep -q "^NO " expected_output/05_*.txt && { echo "FAILED: 05 has a failing check"; status=1; }
  grep -q "^NO " expected_output/09_*.txt && { echo "FAILED: 09 has a failing check"; status=1; }
else
  for n in 01 02 03 04 05 06 07 08 09 10; do g $n "skipped"; done
fi
echo "status=$status"; exit $status
