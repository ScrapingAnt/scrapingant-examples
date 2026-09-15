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
