# Selenium Python: extract complete records from changing elements

Runnable evidence for [finding elements with Selenium Python](https://scrapingant.com/blog/selenium-python-find-element). This example uses a self-authored catalog served on loopback. It makes no ScrapingAnt calls and needs no API key.

## Run from a clean environment

Use Python 3.12, Bash, and installed Chrome. Selenium Manager can locate/download a compatible driver when no driver override is supplied. Dependency installation and initial driver setup may need Internet access; the fixture and browser target are local.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
./run.sh
# Optional: also install Firefox, then run both browsers.
./run.sh --all-browsers
```

`run.sh` runs 16 offline regression tests, one real-Chrome stale-recovery regression, the quickstart, and three matrix rounds per selected browser. A Chrome-only run has 36 extraction observations and 15 diagnostics. Both browsers produce 72 extraction observations and 30 diagnostics. Tests and the quickstart are separate from those denominators. A missing browser, driver, validation failure, or unexpected observation exits nonzero; optional Firefox is not silently skipped after being requested.

New runs write to ignored `run_output/`; the committed `expected_output/` files remain unchanged. `PYTHON_BIN` chooses the interpreter and `OUTPUT_DIR` chooses the output directory. Optional `CHROME_BINARY`, `CHROMEDRIVER`, `FIREFOX_BINARY`, and `GECKODRIVER` select existing installations. Captured metadata records versions, never binary paths. Browser sandboxing is enabled by default; `SELENIUM_NO_SANDBOX=1` is an explicit opt-in only for runners that require it. The loopback listener needs permission to bind a local port.

Each browser starts with a fresh profile. `finally`/context-manager cleanup quits the driver and stops and joins the local HTTP server. The fixture has no remote assets and no secrets are read.

`requirements-lock.txt` pins the installed Selenium dependency set. `expected_output/installed-dependencies.txt` captures the full reused environment; its additional `requests` and `charset-normalizer` packages are not used by this packet.

## Complete quickstart

The packet includes the HTML in `fixtures/`, its loopback server and browser setup in `browser_support.py`, and extraction in `extraction.py`. Run `python quickstart.py` to serve, load, wait, validate and print the three records. `quickstart.py` is:

```python
import json
from selenium.webdriver.common.by import By
from browser_support import browser, fixture_server
from extraction import wait_records

with fixture_server() as origin, browser() as driver:
    driver.get(origin + '/catalog.html?delayed=1')
    driver.find_element(By.ID, 'begin').click()
    print(json.dumps(wait_records(driver), ensure_ascii=False, indent=2))
```

The wait re-runs a locator on every poll, projects every selected row, and returns only when the independent literal oracle accepts all three complete tuples. It retries `NoSuchElementException` and `StaleElementReferenceException` within a five-second timeout. Adapt the validation contract for a real site's expected completeness; a known three-record catalog is a fixture-specific contract, not a universal record count.

The actual captured JSON is [expected_output/quickstart.json](expected_output/quickstart.json). Its records are:

| SKU | Title | Currency | Price | Relative href | Optional badge |
|---|---|---|---|---|---|
| C-101 | Café & Cocoa | USD | 12.50 | /products/cafe | New |
| T-202 | Tea "No. 2" | EUR | 8.00 | /products/tea | null |
| N-303 | Notebook <A5> | GBP | 5.25 | /products/notebook | Sale |

## What the controlled cases show

| Case | Expected observation | Reader action |
|---|---|---|
| `first_scoped` | One C-101 record; incomplete target | Use `find_elements` for a collection. |
| `all_scoped_css` | All three target records | Scope to `#catalog`, then use `.product.active`. |
| `relative_xpath` | All three target records | Start element-relative XPath with `.//`; test class tokens. |
| `unscoped_css` | Outside decoy plus the three targets | Select within the intended container. |
| `class_token` | Three targets, excluding `inactive` | Split class strings into tokens or use CSS class selectors. |
| `class_substring_wrong` | Three targets plus the inactive decoy | A substring test for `active` also matches `inactive`. |
| `presence_only` | Three present shells with empty fields | Presence alone does not prove data is populated. |
| `complete_records_wait` | Three full records after delayed replacement | Wait on the projected data contract. |
| `stale_handle` | `StaleElementReferenceException` | An old handle cannot refer to a replacement node. |
| `refind_after_replacement` | Three full records from new nodes | Re-run the locator after replacement. |
| `iframe_context` | Three records after switching frame | Switch into the frame; restore default content afterward. |
| `open_shadow_root` | Three records through `host.shadow_root` | Query the native open shadow-root search context. |

Five separate diagnostics capture: missing singular lookup (`NoSuchElementException`), missing plural lookup (empty list), compound `By.CLASS_NAME` (`InvalidSelectorException`), visible `.text` versus hidden-inclusive `textContent`, and HTML attributes versus current DOM properties. In the attribute diagnostic, the input's `value` attribute stays `initial`, while `get_property('value')` and `get_attribute('value')` are `edited`. The link's DOM attribute is relative and its property is an absolute loopback URL. The port is normalized to a boolean check, not published.

The presence experiment holds the catalog at empty shells until an explicit button starts a 100 ms delayed population. This makes the negative control deterministic; 100 ms is fixture design, not a measured wait time. The replacement button swaps all catalog children. The additional Chrome regression forces a real replacement between finding nodes and reading them, then requires exactly two searches and the complete dataset. Removing the stale exception handler was observed to make that regression fail.

## Evidence and validation

`oracle.py` contains hand-written expected tuples independent of HTML construction. It rejects missing, extra, duplicate, malformed, or wrong-valued records and validates every field, including a nullable optional badge. Each deliberately wrong case has its own literal expected records or exact exception; any other wrong result fails.

`browser_matrix.py` records raw values in `chrome.json` and `firefox.json`. It does not publish runner-supplied success flags. `summarize.py` recomputes every outcome, requires each case in each of three rounds for each declared browser, checks environment metadata, and requires captures to match current runtime source hashes. It rejects altered diagnostics, unknown or duplicate observations, stale captures and forged flags.

```bash
python summarize.py expected_output/chrome.json expected_output/firefox.json --output run_output/recomputed.json
python verify_hashes.py
```

The committed `verification.json` covers source, documentation, fixtures and captured artifacts (including exploratory records); it excludes itself to avoid a recursive hash. Runtime source hashes are also embedded in each browser capture. Commit references in `evidence.yaml` identify the tested runtime source; its publication provenance links the passing Linux run. `expected_output/exploratory/` preserves the initial restricted-sandbox bind failure, the test-first summary failures, and the intentionally broken stale-recovery mutation. Those are excluded from the final matrix denominator.

## Primary references checked 2026-09-28

- [Selenium element finders](https://www.selenium.dev/documentation/webdriver/elements/finders/): singular/plural APIs, scoping and shadow-root contexts.
- [Selenium Python WebElement API](https://www.selenium.dev/selenium/docs/api/py/selenium_webdriver_remote/selenium.webdriver.remote.webelement.html): stale references, properties, DOM attributes, `get_attribute`, native `shadow_root`.
- [Selenium waiting strategies](https://www.selenium.dev/documentation/webdriver/waits/): explicit waits and application readiness.
- [Selenium frames](https://www.selenium.dev/documentation/webdriver/interactions/frames/): frame switching and default content.
- [Selenium Python By API](https://www.selenium.dev/selenium/docs/api/py/selenium_webdriver_common/selenium.webdriver.common.by.html): locator strategies.
- [Selenium stale-reference troubleshooting](https://www.selenium.dev/documentation/webdriver/troubleshooting/errors/#stale-element-reference-exception): re-locating after DOM changes.

These are controlled correctness observations on a local fixture. They do not measure locator speed, production success rates, scraping evasion, closed shadow roots, cross-origin frames, or every browser/version. AI assisted implementation; the saved outputs come from actual executions.

## Publication verification

Independent local rerun and Linux source CI passed before the evidence pull request was opened. [Linux run](https://github.com/ScrapingAnt/scrapingant-examples/actions/runs/36403582284). The immutable tested source is recorded in `evidence.yaml`; later changes bind metadata and artifact hashes without changing the measured extraction logic. The default command makes no paid API requests.
