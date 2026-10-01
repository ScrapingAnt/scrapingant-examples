# What is an MCP server?

Evidence packet for https://scrapingant.com/blog/what-is-mcp-server

## What this demonstrates
1. `01_handshake_and_tools.py` — the raw Streamable HTTP wire protocol against the live ScrapingAnt MCP server: `initialize`, `notifications/initialized`, `tools/list`, `prompts/list`, `resources/list`, and what `tools/call` returns without an API key. Needs no key.
2. `02_tool_call.py` — a real `tools/call` (`get_web_page_text`, browser on and off) on a public fixture. Needs `SCRAPINGANT_API_KEY`.
3. `03_minimal_server.py` + `03_client.py` — a 25-line MCP server of your own (official `mcp` SDK 2.x, stdio transport) with one tool that fetches Markdown through ScrapingAnt, driven by an in-process client. Listing works without a key; the call needs one.

## Run
```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export SCRAPINGANT_API_KEY=...   # optional; 02 and the tool call in 03 are skipped without it
./run.sh
```

## Files
- `expected_output/` — captured output of the last recorded run (see `evidence.yaml: tested_at`)
- `evidence.yaml` — manifest and claim list

## Limitations
- Recorded without an API key: tool calls are shown as skipped; the credit cost of MCP calls is quoted from the docs, not measured.
- The example server uses `mcp` 2.2.0; the 1.x API (`FastMCP`) differs.

## Offline response regression checks

Run these without installing dependencies or setting a key:

```bash
python3 -m unittest discover -s examples/what-is-mcp-server -p 'test_tool_call.py' -v
```

The tests feed owned JSON/SSE responses to the real parser and exercise the client
with an in-memory transport. They cover notifications before a response, unrelated
request IDs, multiline events, malformed responses, HTTP/JSON-RPC/tool errors,
negotiated protocol/session headers and failure exits. Importing `02_tool_call.py`
does not read a key or make requests. The PR workflow runs only these offline tests.

Following [issue #16](https://github.com/ScrapingAnt/scrapingant-examples/issues/16),
`02_tool_call.py` now matches the requested response ID and reports safe failure
categories rather than indexing a missing `result`. It carries the negotiated
`MCP-Protocol-Version` and optional `Mcp-Session-Id` on subsequent requests, as
specified by the [2025-06-18 transport protocol](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports).
It rejects tool results marked `isError`, separately from JSON-RPC errors, following
the [tool result specification](https://modelcontextprotocol.io/specification/2025-06-18/server/tools).
It prints text-block counts, not response text or error bodies.

This is a bounded diagnostic client, not a complete MCP SDK: it does not reconnect,
resume streams or handle server-initiated requests. It fails on an expired session;
start a new invocation deliberately rather than automatically repeating retrieval.
Direct execution still performs two potentially billable retrievals (browser off,
then on), stopping on the first failure without retry. `run.sh` also exercises a
separate API-backed Markdown call and must not be used as an offline test command.

The October 1 failure log did not capture the server's failing response. Offline
regressions verify client handling; they do not establish the live server failure's
cause or claim that a paid retrieval now succeeds. No new live transcript replaces
the September 15 observations in `evidence.yaml`.
