# Selenium localStorage: seed, restore, and verify extracted records

This self-contained experiment uses Python and Selenium against two self-authored HTTP origins on `127.0.0.1`. It shows how a stored region preference affects actual catalog records. No API key, paid request, account, or external target is used. Chrome is the default; Firefox is an optional second browser. Package installation and Selenium Manager may download dependencies or drivers when they are not already installed.

## Run the complete packet

Use Python 3.12+ and an installed Chrome/Chromium browser:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
./run.sh
```

The default command runs the quickstart, three Chrome rounds, a strict capture rescan, and the regression tests. It writes to ignored `run_output/`; it does not overwrite committed `expected_output/`. If Firefox is installed, use:

```bash
./run.sh --all-browsers
```

`PYTHON_BIN`, `CHROME_BINARY`, `FIREFOX_BINARY`, `CHROMEDRIVER`, and `GECKODRIVER` can select an existing interpreter, browser, or driver. Without driver overrides, Selenium Manager resolves the driver. Browser profiles are temporary and fresh. Chrome's sandbox remains enabled; `SELENIUM_NO_SANDBOX=1` is an explicit opt-in for a trusted CI container that requires it. No key or credential variable is read.

To rescan the committed captures without launching a browser:

```bash
python summarize.py expected_output/chrome.json expected_output/firefox.json --output run_output/summary.json
python -m unittest -v test_packet.py
python verify_hashes.py
```

The tests include a loopback HTTP request with deliberately unusable proxy variables. All direct fixture requests disable ambient proxies and reject non-fixture URLs. The current tests also use the committed Chrome capture as a known-good input for deliberate corruption.

## Complete quickstart

`quickstart.py` is the runnable source for this example; `catalog_fixture.py` starts and cleans up the local server:

```python
import json
from browser_support import browser, wait_catalog
from catalog_fixture import fixture_server
from oracle import exact_dataset
from storage_state import set_item

with fixture_server() as (_, origin), browser() as driver:
    driver.get(origin + '/blank')
    set_item(driver, 'demo_region', 'eu')
    driver.get(origin + '/catalog')
    page = wait_catalog(driver, stored_region='eu', rendered_region='eu')
    assert exact_dataset(page['records'])
    print(json.dumps(page['records'], indent=2))
```

`browser()` selects headless Chrome by default. `set_item` calls `execute_script('localStorage.setItem(arguments[0], arguments[1]);', key, value)`. It passes data as arguments, including quotes, newlines, and Unicode. It never builds executable JavaScript from the value. `wait_catalog` polls the stored preference, application completion, rendered region, and the independent four-record oracle. It does not use an arbitrary runner sleep.

The captured quickstart result in `expected_output/quickstart.json` contains these records:

```json
[
  {"sku": "SKU-1", "currency": "EUR", "price_minor": 825},
  {"sku": "SKU-2", "currency": "EUR", "price_minor": 1675},
  {"sku": "SKU-3", "currency": "EUR", "price_minor": 2425},
  {"sku": "SKU-4", "currency": "EUR", "price_minor": 3350}
]
```

## What the fixture actually does

On startup, `fixtures/catalog.html` chooses the URL's `region` parameter first, then `localStorage.demo_region`, then `us`. It explicitly sends that preference in `/api/catalog?region=...` and renders the JSON response as table rows. LocalStorage does not attach itself to an HTTP request. The independent oracle in `oracle.py` lists all four SKU, currency, and price tuples literally; it does not import the fixture's price table. A separate literal USD oracle validates the wrong-state controls.

The application deliberately schedules an asynchronous preference update using a timer and then fetches and renders the new dataset. The runner records the pre-update state and waits for storage **and** matching records. This is a functional synchronization check, not a timing benchmark.

A late write changes storage immediately, but this application does not reread that preference until a reload or its explicit update function. The fixture does not install a `storage` event handler. Separately, MDN documents that a `storage` event is not fired in the window that made the change; this packet does not measure cross-tab events.

## Extraction observations

Captured on 2026-09-27: Chrome 154.0.8037.57 and Firefox 156.0, three rounds each. Each case below has six observations and four expected target records per observation. A wrong-state control is expected to return the USD dataset, and its records are checked against the USD oracle. It is not relabeled a successful EUR extraction.

| Case | Desired EUR datasets / observations | Matching EUR records / target records |
|---|---:|---:|
| Empty startup | 0/6 | 0/24 |
| Bootstrap, seed, navigate | 6/6 | 24/24 |
| Late write without reload | 0/6 | 0/24 |
| Reload after late write | 6/6 | 24/24 |
| Different port | 0/6 | 0/24 |
| URL-selected rendered page, empty storage | 6/6 | 24/24 |
| `sessionStorage` only | 0/6 | 0/24 |
| Delayed application update and explicit wait | 6/6 | 24/24 |
| Fresh driver with no restoration | 0/6 | 0/24 |
| Manual exact-origin snapshot restoration | 6/6 | 24/24 |
| Direct HTTP with supported query parameter | 6/6 | 24/24 |
| Direct HTTP without query parameter | 0/6 | 0/24 |

There are 72 extraction observations: **60 browser-page observations and 12 direct HTTP controls**. The direct HTTP controls are repeated alongside each browser round; they are not evidence of browser-engine behavior. Eight separate diagnostic cases × three rounds × two browsers = **48 diagnostic observations**. All 120 scenario assertions passed, including the expected wrong-state controls. These counts are not a production success rate.

The diagnostics cover opaque `data:` origins, argument strings, deliberately broken interpolation, JSON round trips, selective removal that retains an unrelated key, wrong-origin restore rejection, asynchronous preconditions, and complete snapshot restoration. See `report.md` and the raw captures for details.

## Manual snapshots and CRUD

`storage_state.py` exposes `set_item`, `get_item`, and `remove_item`, plus an explicit snapshot/restore helper. Strings are the storage boundary; serialize objects with `json.dumps` and decode with `json.loads` or `JSON.parse`. A missing key reads as `None` in Python.

`snapshot(driver, origin)` exports JSON-compatible string pairs for the current document's localStorage. `restore(driver, value, origin)` validates the schema, the snapshot's origin, and the driver's current origin **before mutation**. It then clears and replaces localStorage on that one origin. Navigate to a same-origin bootstrap document before calling it, and navigate to the application afterward. The helper is a manual localStorage export, not a built-in Selenium profile or login export. It does not capture cookies, sessionStorage, IndexedDB, or application state held elsewhere.

Scheme, host, and port define the boundary. The browser experiment changes the port; helper tests also reject changed schemes and hostnames. A new WebDriver driver here creates a fresh profile, so its localStorage begins empty. This does not mean quitting any browser erases localStorage from an existing persistent profile.

## URL-based retrieval boundary

The fixture also supports `/catalog?region=eu`. A fresh browser loads that URL, leaves localStorage empty, and renders the same four EUR records. The direct `/api/catalog?region=eu` endpoint is another explicitly supported fixture contract. Neither path is a universal conversion from localStorage to a URL or cookie.

ScrapingAnt does not support localStorage operations. If a real target already exposes the desired rendered page through a supported URL or cookies, its documented browser rendering can be considered for retrieval. Retain Selenium for state seeding, interactions, or persistent browser state when those are required. This packet makes **no ScrapingAnt request**, proves no handoff, and does not demonstrate arbitrary JSON endpoint compatibility with any service. The local fixture and directly accessible endpoint do not need ScrapingAnt. See [ScrapingAnt browser rendering documentation](https://docs.scrapingant.com/headless-browser).

## Evidence and limits

`expected_output/` contains final raw captures, the rescan summary, the complete quickstart output, and command/test logs. `exploratory_output/` preserves the earlier smoke run and superseded captures; the summary never loads them implicitly. A failed matrix capture is written with completed observations and a sanitized `failure.error_type`; the strict summary rejects it. A process killed before Python cleanup may not write a capture.

`verification.json` hashes the supplied source, fixture, documentation, and capture files. `verify_hashes.py` checks those hashes without rewriting them. A hash manifest detects changes relative to this packet; it does not establish independent provenance. Commit provenance is filled by the publishing step.

Only these browser versions on the captured macOS environment were measured locally. The default Chrome runner is suitable for a Linux CI smoke check, but this packet does not preclaim a Linux result. There is no production reliability, speed, quota, authentication, SSO, encryption, or security guarantee. Private browsing, storage policy denial, frames, cross-tab events, persistent profiles, service workers, and real sites are outside the matrix.

Primary references checked 2026-09-27: [Selenium `execute_script`](https://www.selenium.dev/selenium/docs/api/py/selenium_webdriver_remote/selenium.webdriver.remote.webdriver.html#selenium.webdriver.remote.webdriver.WebDriver.execute_script), [Selenium waits](https://www.selenium.dev/documentation/webdriver/waits/), [MDN localStorage](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage), and [MDN storage events](https://developer.mozilla.org/en-US/docs/Web/API/Window/storage_event).
