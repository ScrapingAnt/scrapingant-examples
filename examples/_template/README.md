# <Article title>

Evidence packet for https://scrapingant.com/blog/<slug>

## What this demonstrates
One paragraph: the reader task, and what running this shows.

## Run
```bash
./run.sh
```
Requirements: Python 3.12, `pip install -r requirements.txt`. Set `SCRAPINGANT_API_KEY` only for steps that call the API (see `evidence.yaml: requires_api_key`).

## Files
- `run.sh` — runs every example and writes `expected_output/*.txt`
- `fixtures/` — inputs (HTML pages, sample data). Public fixtures are served from GitHub Pages.
- `expected_output/` — captured output from the last recorded run (`evidence.yaml: tested_at`)
- `evidence.yaml` — machine-readable manifest used by the article's claim ledger

## Limitations
- …
