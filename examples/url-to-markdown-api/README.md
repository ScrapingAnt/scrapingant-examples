# URL to Markdown API (`/v2/markdown`)

Evidence packet for https://scrapingant.com/llm-ready-data-extraction and https://docs.scrapingant.com/llm-markdown

## What this demonstrates
Every request, response and measurement behind the landing page, run against a ScrapingAnt-owned fixture article served from GitHub Pages (`fixtures/markdown-article.html` at the repo root; a copy is in `fixtures/article.html`) and three public pages.

- `01_request_curl.sh`, `02_request_python.py`, `03_request_node.ts` — the same GET in curl, Python and TypeScript: status, `Ant-credits-cost`, the JSON keys, the first lines of Markdown
- `04_tokens.py` — raw `/v2/general` HTML vs `/v2/markdown` for four pages: bytes, tokens (cl100k_base, o200k_base), ratio
- `05_keep_remove.py` — what the conversion keeps and removes (sentinel checks), and the same conversion run locally with the pinned html2text compared to the API output
- `06_browser_false.py` — `browser=false`: cost 1, Markdown compared with the browser run
- `07_latency.py` — N sequential calls per mode (`LATENCY_N`, default 10): min / median / p90 / max
- `08_errors.py` — wrong key, invalid url, unreachable host, a target that answers 404, a selector that never appears
- `09_js_snippet_cleanup.py` — removing navigation, cookie banner, aside and footer in the browser with `js_snippet` before conversion
- `10_methods.sh` — POST forwarded to the target

## Run
```bash
python -m venv .venv && . .venv/bin/activate   # Python 3.12; Node 22 for 03
pip install -r requirements.txt
export SCRAPINGANT_API_KEY=...                  # about 270 credits per full run (190 with LATENCY_N=3)
./run.sh
```
Without the key every script prints `skipped` and `run.sh` still exits 0.

## Limitations
- Latency is one client on one day; the ratios in `04` depend on the page.
- `_common.cached()` retries once if the API returns an empty Markdown body with HTTP 200 (observed once on 2026-09-24) and prints a note when it happens.
