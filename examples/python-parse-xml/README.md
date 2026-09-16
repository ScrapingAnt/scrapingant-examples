# How to Parse XML in Python

Evidence packet for https://scrapingant.com/blog/python-parse-xml

## What this demonstrates
Every example in the article, run against small fixtures (a catalogue, a sitemap with two namespaces, a Latin-1 file, a broken file, an XSD, a billion-laughs file and an external-entity file) plus a generated 23.8 MB file for the time/memory table. Each of the nine large-file approaches runs in its own subprocess so the peak RSS is per approach.

## Run
```bash
pip install -r requirements.txt
./run.sh
```
Python 3.12. No API key, no network. The large file is generated into `generated/` (git-ignored) on first run.

## Files
- `run.sh` — runs `NN_*.py` in order, writes `expected_output/*.txt`, checks key strings (no timing assertions; machines differ)
- `fixtures/` — inputs; `fixtures/secret.txt` is the file the external-entity case reads
- `01`–`10` — one script per article section (see `evidence.yaml: claims`)
- `expected_output/` — captured output from the last recorded run (`evidence.yaml: tested_at`)

## Limitations
- Timings and peak RSS are from one machine (see `evidence.yaml: environment`); the ratios between approaches are the point, not the absolute numbers.
- The ScrapingAnt API is not called (no key); the article's product paragraph stays within the documented parameters.
