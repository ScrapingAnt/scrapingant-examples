#!/usr/bin/env bash
# 00, 01 and 03_client run without a key; 02 and the tool call inside 03 need SCRAPINGANT_API_KEY.
# 03_client_bad_key records what a failing tool call looks like on your own server.
set -uo pipefail
cd "$(dirname "$0")"; mkdir -p expected_output; status=0
run() { name="$1"; shift; echo "== $name"; "$@" 2>&1 | tee "expected_output/$name.txt"; [ "${PIPESTATUS[0]}" -eq 0 ] || { echo "FAILED: $name"; status=1; }; }
run 00_handshake_minimal python 00_handshake_minimal.py
run 01_handshake_and_tools python 01_handshake_and_tools.py
if [ -n "${SCRAPINGANT_API_KEY:-}" ]; then run 02_tool_call python 02_tool_call.py; else echo "== 02_tool_call: SKIPPED (SCRAPINGANT_API_KEY not set)"; fi
run 03_client python 03_client.py
run 03_client_bad_key env SCRAPINGANT_API_KEY=not-a-real-key python 03_client.py
exit $status
