# How to Read HTML Tables With Pandas (pandas 3.0.5)

Evidence packet for https://scrapingant.com/blog/pandas-read-html-table

## What this demonstrates
Every `pandas.read_html()` option and error on the page, run against `fixtures/tables.html` (eleven tables, each built to trigger one behaviour: `<thead>` two-row headers, `colspan`/`rowspan`, thousands separators and currency, leading zeros, European decimals, dates, links, a `display:none` row, a nested table, a `<td>` header row) and `fixtures/broken.html`, on pandas 3.0.5 with lxml 6.1.3, beautifulsoup4 4.15.0 and html5lib 1.1. The same fixture is served from GitHub Pages (`fixtures/html-tables.html` at the repo root) for the URL cases.

- `01_basics.py` — file, raw string (raises on pandas 3), `StringIO`, binary file object, URL; the list you get back
- `02_select.py` — `match` (text, regex), `attrs`, combinations, and the "No tables found" errors
- `03_headers.py` — MultiIndex from a two-row `<thead>` and how to flatten it, `header=`, spans, `<td>` header rows, `index_col`, `skiprows`
- `04_numbers.py` — `thousands`, `converters` (currency, percent, leading zeros), `decimal`, `na_values`/`keep_default_na`, dates, `dtype_backend`
- `05_links.py` — `extract_links`
- `06_hidden_nested.py` — `displayed_only`; what a nested table produces
- `07_parsers.py` — `flavor` on broken markup; the ImportError for each missing library (subprocess); wall time on a generated 20,000-row table (lxml vs bs4, median of 5)
- `08_http.py` — pandas' own fetch (urllib, default user agent) against Wikipedia, `storage_options` headers, `requests` + `StringIO`, the BeautifulSoup hand-off
- `09_old_page_errors.py` — the 2024 page's idioms that no longer run (`df.append`, `chunksize=`, `usecols=`, positional `match`)
- `10_scrapingant.py` — a table fetched through the ScrapingAnt API with `browser=true`, then `read_html`; runs only with `SCRAPINGANT_API_KEY`, otherwise prints "skipped"

## Run
```bash
python -m venv .venv && . .venv/bin/activate   # Python 3.12
pip install -r requirements.txt
./run.sh
```
Needs outbound HTTPS for 01 and 08 (GitHub Pages fixture, one Wikipedia page).

## Limitations
- The Wikipedia rows record what Wikipedia returned on the test date for pandas' default user agent; that can change.
- Seconds in `07_parsers.txt` depend on the machine; the ratio between flavors is the claim.
