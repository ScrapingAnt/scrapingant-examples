"""The MCP handshake with nothing but HTTP: initialize, initialized, tools/list.

No API key is needed for these three calls. This is the exact block shown in
the article; 01_handshake_and_tools.py is the longer version.
"""
import json

import requests

ENDPOINT = "https://api.scrapingant.com/mcp/"  # trailing slash: /mcp answers with a redirect
HEADERS = {"Content-Type": "application/json",
           "Accept": "application/json, text/event-stream"}  # the spec requires both


def parse(resp):
    """Streamable HTTP lets the server answer with plain JSON or an SSE stream."""
    if resp.headers.get("content-type", "").startswith("text/event-stream"):
        data = [l[5:] for l in resp.text.splitlines() if l.startswith("data:")]
        return json.loads(data[-1]) if data else None
    return resp.json() if resp.text else None


s = requests.Session()
init = parse(s.post(ENDPOINT, headers=HEADERS, timeout=60, json={
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {},
               "clientInfo": {"name": "blog-example", "version": "1.0"}}}))
HEADERS["MCP-Protocol-Version"] = init["result"]["protocolVersion"]  # required on every later request
s.post(ENDPOINT, headers=HEADERS, timeout=60, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
tools = parse(s.post(ENDPOINT, headers=HEADERS, timeout=60, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}))

info = init["result"]
print(f"server: {info['serverInfo']['name']} {info['serverInfo']['version']}, protocol {info['protocolVersion']}")
print(f"capabilities: {sorted(info['capabilities'])}")
for t in tools["result"]["tools"]:
    props = t["inputSchema"]["properties"]
    print(f"tool: {t['name']}({', '.join(props)})  required={t['inputSchema'].get('required')}")
