"""Call a ScrapingAnt MCP tool over Streamable HTTP with an API key (needs SCRAPINGANT_API_KEY)."""
import json
import os

import requests

ENDPOINT = "https://api.scrapingant.com/mcp/"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
           "x-api-key": os.environ["SCRAPINGANT_API_KEY"]}
FIXTURE = "https://scrapingant.github.io/scrapingant-examples/fixtures/dynamic-delayed.html"


def parse(resp):
    if resp.headers.get("content-type", "").startswith("text/event-stream"):
        return next(json.loads(l[5:]) for l in resp.text.splitlines() if l.startswith("data:"))
    return resp.json()


s = requests.Session()
init = parse(s.post(ENDPOINT, headers=HEADERS, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "blog-example", "version": "1.0"}}}, timeout=60))
s.post(ENDPOINT, headers=HEADERS, json={"jsonrpc": "2.0", "method": "notifications/initialized"}, timeout=60)
for browser in (False, True):
    r = s.post(ENDPOINT, headers=HEADERS, json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
        "name": "get_web_page_text", "arguments": {"url": FIXTURE, "browser": browser}}}, timeout=120)
    out = parse(r)
    text = "".join(c.get("text", "") for c in out["result"]["content"])
    print(f"get_web_page_text browser={browser}: isError={out['result'].get('isError', False)} text={text.strip()[:80]!r}")
