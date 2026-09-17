# BeautifulSoup Cheat Sheet (bs4 4.15)

Evidence packet for https://scrapingant.com/blog/beautifulsoup-cheatsheet

## What this demonstrates
Every snippet in the article and on the shareable cards, run against `fixtures/page.html` (a small catalogue) and `fixtures/broken.html` (a misnested fragment) on beautifulsoup4 4.15.0: parsing from str/file/response, the three parsers on broken markup, `find`/`find_all` and `select` forms, navigation, text and attributes, modification, output formatters, tables with pandas, the 4.13+ deprecation warnings, the common errors, a CPU-time comparison of the parsers on a generated 3.1 MB page, and a dated popularity snapshot (`popularity.py`).

## Run
```bash
pip install -r requirements.txt
./run.sh                      # REFRESH_POPULARITY=1 ./run.sh to re-fetch the popularity snapshot
```
Python 3.12. Case 01 fetches one public fixture over HTTPS; case 11 installs beautifulsoup4 into a scratch directory (pip or uv) to reproduce `FeatureNotFound`. `run.sh` sets `PYTHONWARNINGS=default` so the deprecation warnings are visible.

## Files
- `run.sh` — runs `NN_*.py`, writes `expected_output/*.txt`, checks key strings
- `_common.py` — fixture loading, the one-line exception printer, warnings to stdout
- `01`–`13` — one script per article section; `12_speed.py` generates `generated/large.html` (git-ignored); `13_typing.py` is run through mypy
- `popularity.py` — PyPI 30-day rank/downloads (hugovk/top-pypi-packages) and Stack Overflow tag counts → `expected_output/popularity.json`
- `expected_output/` — captured output from the last recorded run (`evidence.yaml: tested_at`)

## Limitations
- CPU seconds in `12_speed.txt` depend on the machine; the ratios between cases are the claim.
- The popularity numbers are a snapshot with dates inside the JSON.
