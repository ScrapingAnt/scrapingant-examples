"""Talk to the ScrapingAnt MCP server with nothing but HTTP.

Shows the wire protocol an MCP client speaks (Streamable HTTP transport,
JSON-RPC 2.0): initialize -> notifications/initialized -> tools/list.
No API key is needed for these calls; only tools/call requires one.
"""
import json
import os
import sys

import requests

ENDPOINT = "https://api.scrapingant.com/mcp/"  # trailing slash: /mcp redirects here
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
if os.environ.get("SCRAPINGANT_API_KEY"):
    HEADERS["x-api-key"] = os.environ["SCRAPINGANT_API_KEY"]


def parse(resp: requests.Response) -> dict | None:
    """Streamable HTTP lets the server answer with plain JSON or an SSE stream."""
    if resp.headers.get("content-type", "").startswith("text/event-stream"):
        for line in resp.text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:])
        return None
    return resp.json() if resp.text else None


def rpc(session: requests.Session, method: str, params: dict | None = None, id_: int | None = 1) -> dict | None:
    msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
    if id_ is not None:
        msg["id"] = id_
    r = session.post(ENDPOINT, headers=HEADERS, json=msg, timeout=60)
    print(f"POST {method:28} -> HTTP {r.status_code} {r.headers.get('content-type', '')}")
    if "mcp-session-id" in r.headers:
        session.headers["Mcp-Session-Id"] = r.headers["mcp-session-id"]
        print(f"  Mcp-Session-Id received (len {len(r.headers['mcp-session-id'])})")
    return parse(r)


s = requests.Session()
init = rpc(s, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                             "clientInfo": {"name": "blog-example", "version": "1.0"}})
res = init["result"]
print(f"  server: {res['serverInfo']['name']} {res['serverInfo']['version']}, protocol {res['protocolVersion']}")
print(f"  capabilities: {sorted(res['capabilities'])}")
s.headers["MCP-Protocol-Version"] = res["protocolVersion"]

rpc(s, "notifications/initialized", id_=None)

tools = rpc(s, "tools/list", id_=2)["result"]["tools"]
print(f"  {len(tools)} tools")
for t in tools:
    props = t["inputSchema"].get("properties", {})
    req = t["inputSchema"].get("required", [])
    print(f"  - {t['name']}: {t.get('description', '').strip().splitlines()[0][:100]}")
    for p, spec in props.items():
        typ = spec.get("type") or "|".join(a.get("type", "?") for a in spec.get("anyOf", []))
        default = f" = {json.dumps(spec['default'])}" if "default" in spec else ""
        print(f"      {p}{'*' if p in req else ''}: {typ}{default}")

for method in ("prompts/list", "resources/list"):
    out = rpc(s, method, id_=3)
    key = method.split("/")[0]
    items = (out or {}).get("result", {}).get(key, [])
    print(f"  {len(items)} {key}: {[i['name'] for i in items][:5]}")

if "x-api-key" not in HEADERS:
    call = rpc(s, "tools/call", {"name": "get_web_page_text", "arguments": {"url": "https://example.com", "browser": False}}, id_=4)
    print("  tools/call without an API key ->", json.dumps(call)[:200])
    sys.exit(0)
