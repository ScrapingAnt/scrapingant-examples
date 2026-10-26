#!/usr/bin/env bash
# Starts local proxy.py proxies (8899 with Basic auth lab / p@ss#w0rd, 8901 without auth),
# then drives Playwright MCP through them against http://httpbin.org/headers.
# The proxies stamp plain-HTTP requests with X-Lab-Proxy, so the echoed headers show which proxy carried the request.
set -uo pipefail
cd "$(dirname "$0")"
OUT=expected_output; mkdir -p "$OUT"
export PYTHONPATH=$PWD
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY no_proxy NO_PROXY
P="python -m proxy --hostname 127.0.0.1 --num-workers 1 --num-acceptors 1"
$P --port 8899 --basic-auth 'lab:p@ss#w0rd' --plugins lab_plugins.AuthProxy > "$OUT/proxy-8899.log" 2>&1 & A=$!
$P --port 8901 --plugins lab_plugins.ProxyA > "$OUT/proxy-8901.log" 2>&1 & B=$!
trap 'kill $A $B 2>/dev/null' EXIT
for port in 8899 8901; do for i in $(seq 50); do nc -z 127.0.0.1 $port && break; sleep 0.1; done; done

{ node --version; for p in @playwright/mcp playwright @modelcontextprotocol/sdk; do echo "$p $(node -p "require('./node_modules/$p/package.json').version")"; done; python --version; uv pip freeze --python "$(command -v python)" 2>/dev/null | grep -i '^proxy-py'; } > "$OUT/00_versions.txt"
cat "$OUT/00_versions.txt"

fail=0
run() { local name=$1; shift; echo "--- $name"; echo "\$ $*"; "$@" 2>&1 | tee "$OUT/$name.txt"; [ "${PIPESTATUS[0]}" = 0 ] || fail=1; }
URL=http://httpbin.org/headers
run 01_proxy_server node cases/navigate.mjs $URL --proxy-server http://127.0.0.1:8901
run 02_proxy_bypass node cases/navigate.mjs $URL --proxy-server http://127.0.0.1:8901 --proxy-bypass httpbin.org
run 03_credentials_in_url node cases/navigate.mjs $URL --proxy-server 'http://lab:p%40ss%23w0rd@127.0.0.1:8899'
run 04_config_auth node cases/navigate.mjs $URL --config configs/proxy-auth.json
run 05_config_wrong_password node cases/navigate.mjs $URL --config configs/proxy-auth-wrong.json
run 06_env_var env PLAYWRIGHT_MCP_PROXY_SERVER=http://127.0.0.1:8901 node cases/navigate.mjs $URL
run 07_playwright_auth node cases/playwright_auth.mjs
run 09_dead_proxy node cases/navigate.mjs $URL --proxy-server http://127.0.0.1:8903
if [ -n "${SCRAPINGANT_API_KEY:-}" ]; then run 08_scrapingant_mcp node cases/scrapingant_mcp.mjs; else echo "--- 08 skipped (no SCRAPINGANT_API_KEY)"; fi
rm -rf .playwright-mcp
exit $fail
