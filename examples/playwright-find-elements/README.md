# Playwright locators to validated records

This local, no-key packet demonstrates a complete Python Playwright extraction: choose an intentional scope, wait for the fixture's ready signal, project records, and validate them against an independent literal oracle. It also captures wrong selections and diagnostic outcomes. It does not call ScrapingAnt or any external target.

## Run

Use Python 3.12. Browser installation may download the pinned Playwright browser builds; the examples themselves request only the loopback fixture.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium firefox
python quickstart.py
./run.sh
```

On Linux, install browser system dependencies with Playwright's documented installation procedure. Chromium is launched with `chromium_sandbox=True`; the packet never adds `--no-sandbox`. Execution environments must allow a loopback listener and browser child processes. Server, page, and browser cleanup use `finally` blocks or context managers.

`run.sh` defaults to three rounds each in Chromium and Firefox, with no credentials. It writes to ignored `run_output/`, so reruns do not overwrite the captured evidence. `PYTHON_BIN` and `OUTPUT_DIR` can select a runtime/output folder. No automatic dependency installation, API call, or retry occurs.

The small program `quickstart.py` owns the full server/browser lifecycle. `extract.py` shows both row-by-row locator reads and a single `evaluate_all` projection. The latter receives the locator's matched DOM nodes in browser JavaScript; it is not Python code and cannot access Python variables without explicit arguments.

## Captured quickstart output

`expected_output/quickstart.json` contains the actual three records:

| SKU | Title | Currency | Price | Relative href |
|---|---|---|---|---|
| K-101 | Copper Kettle | USD | 24.50 | /products/kettle |
| M-202 | Café Mug | EUR | 12.00 | /products/mug |
| T-303 | Tea & Honey | GBP | 8.75 | /products/tea |

Price strings deliberately retain two decimal places. This fixture does not establish a universal currency/price parser.

## Evidence structure

- `fixtures/` contains independently authored literal HTML. It never imports the oracle or generates its catalog from expected records.
- `oracle.py` contains separately written literal expected record tuples and strict schema/summary validation.
- `expectations.py` names each intended result, including the sponsored decoy and loading placeholder.
- `browser_matrix.py` captures actual observations without writing success flags. `summarize.py` recomputes acceptance from the complete matrix.
- `expected_output/` is the captured run. `report.md` explains its scope and denominators.
- `test_oracle.py` and `test_integrity.py` reject malformed records, incomplete/tampered runs, and changed/missing artifacts.
- `exploratory/` preserves the failing first attempt and test-first red results.
- `manifest.json` inventories SHA-256 hashes of the frozen sources, fixtures, documentation, and outputs. `python integrity.py` verifies it. A hash manifest detects drift; it is not a signature or independent review.

Do not publish `run_output/`, `.venv/`, or browser profiles. This packet creates no persistent browser profile.

## Reader-actionable failures

| Observed failure/control | Action |
|---|---|
| Singular `.inner_text()` matched four titles and raised strictness error | Narrow the locator or explicitly extract a collection. |
| `.first` returned the sponsored AD-000 record | Define the intended parent scope; the first match is not a correctness check. |
| During controlled loading, `count()` and `all()` reported one placeholder | Wait for an application signal indicating the intended dataset is ready. |
| Ancestor-prefixed `has=` locator found no matching row | Write the inner locator relative to each candidate row. |
| Missing locator timed out | Report/handle absence explicitly; do not turn it into a valid empty dataset. |
| Hidden text appeared in `text_content()` but not `inner_text()` | Select the text contract your downstream data needs. |
| `get_attribute('href')` returned a relative URL; DOM `.href` was absolute | Choose raw attribute or resolved property deliberately. |
| Raw document CSS and XPath did not enter the open shadow root | Use the tested Playwright locator behavior or explicitly traverse the shadow root in raw JavaScript. |

## Primary references

Accessed 2026-09-28:

- [Locators](https://playwright.dev/python/docs/locators): strictness, relative filters, role/text selectors, re-resolution, and open shadow behavior.
- [Locator API](https://playwright.dev/python/docs/api/class-locator): `all`, `count`, `evaluate_all`, `inner_text`, `text_content`, and `get_attribute`.
- [Browser JavaScript evaluation](https://playwright.dev/python/docs/evaluating): separate browser and Python execution environments.
- [FrameLocator](https://playwright.dev/python/docs/api/class-framelocator): explicitly entering a frame.
- [Browser installation](https://playwright.dev/python/docs/browsers): installing the browsers and system dependencies.

The tested source and passing Linux CI are recorded in `evidence.yaml`. Measurements apply to this controlled fixture and captured versions, not production success rates or performance.

## Publication verification

Independent local rerun and Linux source CI passed before the evidence pull request was opened. [Linux run](https://github.com/ScrapingAnt/scrapingant-examples/actions/runs/36404427667). The immutable tested source is recorded in `evidence.yaml`; later changes bind metadata and artifact hashes without changing the measured extraction logic. The default command makes no paid API requests.
