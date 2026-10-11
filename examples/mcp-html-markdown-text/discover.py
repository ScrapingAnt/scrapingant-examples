#!/usr/bin/env python3
"""Optional public, unauthenticated MCP discovery; NEVER calls retrieval tools."""
import datetime as dt
import json
from pathlib import Path
import requests

ENDPOINT = "https://api.scrapingant.com/mcp/"


def parse(response):
    response.raise_for_status()
    if response.headers.get("content-type", "").startswith("text/event-stream"):
        data = [line[5:].strip() for line in response.text.splitlines() if line.startswith("data:")]
        return json.loads(data[-1]) if data else None
    return response.json() if response.content else None


def run(out):
    # Deliberately no credential/environment lookup and no tools/call code path.
    session = requests.Session()
    session.trust_env = False
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    transcript = {"started_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "endpoint": ENDPOINT,
                  "authenticated": False, "retrieval_tool_calls": 0, "model_calls": 0, "exchanges": []}

    def exchange(payload):
        r = session.post(ENDPOINT, headers=headers, json=payload, timeout=20, allow_redirects=False)
        transcript["exchanges"].append({"request": payload, "http_status": r.status_code,
                                       "content_type": r.headers.get("content-type"), "raw_response": r.text})
        return parse(r)

    try:
        initialized = exchange({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-11-25", "capabilities": {},
            "clientInfo": {"name": "issue8-public-discovery", "version": "1.0"}}})
        headers["MCP-Protocol-Version"] = initialized["result"]["protocolVersion"]
        exchange({"jsonrpc": "2.0", "method": "notifications/initialized"})
        tools = exchange({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        transcript["server_info"] = initialized["result"]["serverInfo"]
        transcript["negotiated_protocol"] = initialized["result"]["protocolVersion"]
        transcript["tools"] = tools["result"]["tools"]
        transcript["complete"] = True
    except Exception as exc:
        transcript["complete"] = False
        transcript["error_type"] = type(exc).__name__
        raise
    finally:
        out.write_text(json.dumps(transcript, indent=2) + "\n")
    print(f"Public discovery: {transcript['server_info']}; protocol {transcript['negotiated_protocol']}")
    for tool in transcript["tools"]:
        print(f"{tool['name']}: {', '.join(tool['inputSchema']['properties'])}")
    print("Retrieval tool calls: 0. Credentials read: 0. Model calls: 0.")


if __name__ == "__main__":
    run(Path(__file__).resolve().parent / "expected_output" / "public-discovery.json")
