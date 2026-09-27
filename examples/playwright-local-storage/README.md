# Playwright localStorage evidence

A complete Python example for setting a preference before application startup, restoring exact-origin state, and checking the resulting records. The self-authored catalog runs on `127.0.0.1` with ephemeral ports. Runtime tests need no credentials, external targets, or paid requests.

## Run

Python 3.12 was used for the committed captures. From the repository root:

```bash
cd examples/playwright-local-storage
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-lock.txt
python -m playwright install chromium
./run.sh
```

On Linux, install browser system dependencies with `python -m playwright install --with-deps chromium`. Downloads occur during installation; the runner itself uses local fixtures. The default requires Chromium only. For both captured browsers:

```bash
python -m playwright install firefox
./run.sh --all-browsers
```

The runner executes the offline boundary tests, complete quickstart, three rounds per browser, and a summary that rescores raw rows. It exits nonzero on failed checks or malformed captures. `PYTHON_BIN` selects an existing Python executable, `OUTPUT_DIR` selects the capture directory, and `PLAYWRIGHT_BROWSERS_PATH` selects a browser cache. No code reads API keys or `.env` files.

Normal runs write to ignored `run_output/`, preserving committed observations in `expected_output/`. Context managers and `finally` blocks close contexts, browser processes, and fixture servers, including on failure. No persistent browser profile or state file is needed.

## Complete quickstart

```bash
python quickstart.py --output run_output/quickstart.json
```

[quickstart.py](quickstart.py) starts the fixture, registers an exact-origin `add_init_script`, opens the catalog, extracts DOM rows, and validates them against independently authored literal tuples. Download this entire directory because the script imports its adjacent fixture, initializer and oracle helpers.

The initializer writes `region=eu` only when that key is missing. It uses JSON serialization for its fixed configuration. The CRUD and JSON diagnostics use `page.evaluate` arguments for values rather than interpolating user data into JavaScript source. The loopback-only origin validator is deliberately narrower than a general browser automation helper.

The full [captured quickstart output](expected_output/quickstart.json) includes the actual page URL, catalog response URL, API rows, DOM rows, and environment. These four tuples matched:

| SKU | Currency | Price |
|---|---|---:|
| ATLAS-01 | EUR | 12.50 |
| BIRCH-02 | EUR | 24.00 |
| CORAL-03 | EUR | 8.75 |
| DELTA-04 | EUR | 41.20 |

## Application contract and measurement

At startup, the fixture reads an explicit page `?region=eu` or `?region=us` parameter first, then `localStorage.region`, then defaults to `us`. It explicitly sends the chosen value to `/api/catalog?region=...`. A URL-selected preference is not written to localStorage. The table is rendered from that API response once; a later storage write alone does not rerender this fixture.

[spec.py](spec.py) declares 12 extraction cases and four diagnostics before execution. Three rounds in each of Chromium and Firefox produce 72 extraction observations and 24 diagnostics. Each extraction compares four SKU/currency/price tuples with [state.py](state.py), which does not import the catalog fixture. The oracle rejects missing, duplicate, extra and incorrectly typed rows. Negative controls must also match the independent US tuple set, so arbitrary zero-match data cannot pass as a useful control.

See [report.md](report.md) for per-case results and limits. All 72 extractions returned HTTP 200 and four rows, while 36 matched the desired EU tuples. The 96/96 passed checks mean that the deliberately correct and deliberately wrong-state cases behaved as predicted; they are not a scraping success rate.

## Inspect and recompute

```bash
python -m unittest -v
python browser_matrix.py --browser chromium --output run_output/chromium.json
python browser_matrix.py --browser firefox --output run_output/firefox.json
python summarize.py --input-dir run_output --browsers chromium firefox --output run_output/comparison.json
```

Recompute the committed summary without a browser or network:

```bash
python summarize.py --output run_output/comparison-from-captures.json
cmp comparison.json run_output/comparison-from-captures.json
```

The builder checks browser identity and requested coverage, exactly three rounds, every declared case once per round, case types, timestamps, origins, stored score consistency, the request actually made, and each diagnostic's observations. Tests corrupt captures and verify rejection. Failed experimental runs remain under `expected_output/exploratory/` and are excluded from primary counts; quickstart and unit tests also have separate denominators. Source/capture SHA-256 hashes and review status are recorded in [verification.json](verification.json).

## Retrieval boundary

The URL-selected case renders the same desired records with no stored preference. That is a contract implemented by this fixture, not a general conversion from localStorage to a URL or cookie. A target that exposes the desired page through a reproducible URL may be a candidate for ScrapingAnt's documented [browser-rendered HTML retrieval](https://docs.scrapingant.com/headless-browser). ScrapingAnt does not support localStorage operations. Retain browser automation when startup seeding, interactions, or persistent browser state are necessary. No ScrapingAnt request or handoff was made here, and it is unnecessary for this local fixture.

## Scope

Captured on 2026-09-27: Python 3.12.10, Playwright 1.63.0, Chromium 153.0.8010.12, Firefox 155.0, Darwin 25.6.0 arm64. [requirements-lock.txt](requirements-lock.txt) pins the complete installed runtime set; [dependencies.txt](expected_output/dependencies.txt) is actual `pip freeze` output. Default CI coverage is Chromium; Firefox requires its optional installation.

This deterministic local mechanism experiment does not measure speed or production reliability. It tests same-origin localStorage, a changed port, a wrong-origin initializer, and synthetic sessionStorage behavior. It does not test real login, MFA, SSO, cross-browser authentication transfer, browser restarts, storage quota, blocked storage, HTTPS transitions, IndexedDB, OPFS, passkeys, or third-party storage partitioning. The two-browser repeats share one host and one fixture design.

Primary documentation checked 2026-09-27: [initializers](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-add-init-script), [storage state](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-storage-state), [evaluation arguments](https://playwright.dev/python/docs/evaluating#evaluation-argument), [localStorage](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage), and [storage events](https://developer.mozilla.org/en-US/docs/Web/API/Window/storage_event). [evidence.yaml](evidence.yaml) maps individual claims to documentation or captures. AI assistance was used for implementation and analysis; review status is recorded separately without implying human approval.
