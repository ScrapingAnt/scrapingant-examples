# Scrape a Dynamic Website with Python

Evidence packet for https://scrapingant.com/blog/scrape-dynamic-website-with-python

## What this demonstrates
Two fixture pages replace their content with JavaScript: one on `DOMContentLoaded`, one 1500 ms later (simulating an async request). A plain HTML parser sees the original text; Selenium 4, Playwright and the ScrapingAnt API see the rendered text, and each needs an explicit wait for the delayed case.

## Run
```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
export SCRAPINGANT_API_KEY=...   # optional; 04_scrapingant_api.py is skipped without it
./run.sh
```
Selenium 4 resolves chromedriver itself (Selenium Manager); Google Chrome must be installed.

## Files
- `01_beautifulsoup_only.py` — parser only, shows the failure
- `02_selenium.py` — Selenium 4 headless Chrome, `WebDriverWait` for the delayed page
- `03_playwright.py` — Playwright sync API, `wait_for_selector`
- `04_scrapingant_api.py` — API call with and without a browser, `wait_for_selector`, credit cost from the `Ant-credits-cost` header
- `fixtures/` — local copies of the two pages; public copies at https://scrapingant.github.io/scrapingant-examples/fixtures/
- `expected_output/` — captured output, see `evidence.yaml: tested_at`

## Limitations
- Fixtures are tiny synthetic pages; they show the mechanism, not real-site anti-bot behaviour.
- `04_scrapingant_api.py` output is only recorded when run with a key; CI runs it only if the repo secret is set.
