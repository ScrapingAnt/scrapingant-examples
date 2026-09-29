# MCP extraction refresh — partial preparation

Status: **not an executed AI extraction workflow and not publication-ready**.

On 2026-09-29, `discover.py` successfully initialized the public ScrapingAnt MCP endpoint using Python 3.12.11 and mcp 2.2.0, and saved its actual advertised tool schemas in `expected_output/discovery.json`. The negotiated protocol was 2025-11-25; server version 1.30.0. The returned tools were `get_web_page_html`, `get_web_page_markdown`, and `get_web_page_text`.

This discovery needs no API key and makes no target-page retrieval or model call. An initial invocation saved discovery but failed while printing a renamed SDK attribute; the corrected script completed on the second invocation. Neither invocation called a retrieval tool.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python discover.py
```

The local HTML fixtures and separately authored `fixtures/oracle.json` are preparatory inputs only. They have not been uploaded or fetched through MCP, and no model has extracted records from them. They still need reconciliation with every approved brief case, an application schema, offline failure controls, a pinned prompt/model configuration, and real captured retrieval/extraction runs.

## Remaining prerequisites

The owner approved the reader task and a proposed maximum of five fixture retrievals and fifteen model runs. A model-provider configuration and explicit spending ceiling are still pending. An existing ScrapingAnt key is available locally but was not read or used by this packet. Do not publish credentials.

After access is settled, implement and validate the remaining harness, publish owned fixtures, run the bounded live workflow, persist real model results, independently review the evidence and draft, and only then restore the article's indexability. The current article remains unlisted.

**Calls to date:** zero target-page retrievals; zero model calls; zero paid API calls. Public protocol discovery alone is not evidence of extraction quality.
