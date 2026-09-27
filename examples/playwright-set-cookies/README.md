# Playwright cookies and state evidence

A no-secret Python example for setting cookies before navigation, preserving application state, and sharing or isolating API cookies. It runs only against a self-authored HTTP server on `127.0.0.1` and makes no paid requests. Every cookie and product is synthetic.

## Run

Python 3.12 was used for the captures. Install the full pinned runtime lock and bundled Chromium:

```bash
cd examples/playwright-set-cookies
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
./run.sh
```

On Linux, install the browser OS dependencies with `python -m playwright install --with-deps chromium`. The default run requires only Chromium and no credentials. To include Firefox:

```bash
python -m playwright install firefox
./run.sh --all-browsers
```

The full run executes boundary/regression tests, the compact quickstart, three rounds per selected browser, and the summary builder. It exits nonzero on a failed case or invalid capture. `PYTHON_BIN` selects an existing Python executable; `OUTPUT_DIR` changes the output directory. `PLAYWRIGHT_BROWSERS_PATH` can select a browser cache. No script reads `.env` or enables an external service when credentials happen to exist.

Normal reruns write to ignored `run_output/`. The committed `expected_output/` files are captured observations; they are not overwritten by the default command. The fixture, nonpersistent browser contexts, browser processes and temporary state files are closed by context managers and `finally` blocks.

## Quickstart

```bash
python quickstart.py --output run_output/quickstart.json
```

[quickstart.py](quickstart.py) adds a synthetic cookie before navigation, sets the fixture's localStorage region, saves state to a temporary file, restores it into a fresh context, and extracts both browser DOM records and shared-jar API JSON. Helpers live beside it, so download the whole example directory.

Only this fixture recognizes the made-up `member-v1` value. Inventing a cookie does not authenticate to a real website. A real state snapshot can contain sensitive authentication material; this example stores only synthetic values in a temporary directory and removes it when done.

See the complete [captured quickstart output](expected_output/quickstart.json). Both extracted lists matched these independent literal expected tuples:

| SKU | Currency | Price |
|---|---|---:|
| SKU-101 | EUR | 8.10 |
| SKU-202 | EUR | 16.20 |
| SKU-303 | EUR | 24.30 |
| SKU-404 | EUR | 32.40 |

## What is measured

The fixture's `demo_session` cookie chooses member versus retail prices. The page reads `localStorage.region` and explicitly sends it as `?region=EU` or `?region=US` to `/api/catalog`. API requests do not execute that page script; `region_params()` translates this fixture's state into the request parameter, requiring an exact origin match.

There are 12 extraction cases and six diagnostics per browser round. Every extraction expects four unique SKU/currency/price tuples. A `Counter` intersection caps each matching tuple at its expected multiplicity, and exact equality also rejects missing or extra records. Status 200 and four rows are recorded separately from record correctness.

[report.md](report.md) explains the 72 primary extraction observations, 36 diagnostics, failure controls, measured route hit counts and limitations. [comparison.json](comparison.json) is derived from the Chromium/Firefox captures. Quickstart and exploratory observations are excluded from those denominators.

## Reproduce individual checks

```bash
python -m unittest -v
python offline_checks.py --output run_output/offline-checks.json
python browser_matrix.py --browser chromium --rounds 3 --output run_output/chromium.json
python browser_matrix.py --browser firefox --rounds 3 --output run_output/firefox.json
python summarize.py --input-dir run_output --output run_output/comparison.json
```

`offline_checks.py` runs the complete unittest suite and deliberately substitutes a naive duplicate-row scorer in memory to prove the regression test fails. That deliberately failing mutant is reported separately from passing production tests; no source file is modified.

To regenerate the summary from committed captures without launching browsers or making network calls:

```bash
python summarize.py --output run_output/comparison-from-captures.json
cmp comparison.json run_output/comparison-from-captures.json
```

The builder independently rescans each records list, checks its stored scores/check flag, requires all expected cases exactly once in each consecutive round, and rejects duplicate browser captures. The `test_summary.py` tests use the first committed Chromium round as a real capture to mutate; they do not rerun a browser.

## Scope and documentation

The captures were made on 2026-09-27 with Playwright 1.63.0, bundled Chromium 153.0.8010.12, bundled Firefox 155.0, Python 3.12.10 and macOS 26.6.2 arm64. The full transitive dependency lock is [requirements-lock.txt](requirements-lock.txt).

This is a deterministic mechanism experiment, not a production reliability estimate or an authentication portability test. The use of localStorage for region is this fixture's design. The HTTP loopback setup does not measure `Secure` delivery, cross-site `SameSite`, partitioned cookies, real login, MFA, SSO or server-bound sessions. Only cookies and localStorage state are exercised; sessionStorage, IndexedDB, OPFS and passkey persistence are outside the experiment. The [Playwright auth documentation](https://playwright.dev/python/docs/auth) discusses state persistence, and the [BrowserContext reference](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-storage-state) documents optional storage fields; do not infer that `storage_state()` contains only the two mechanisms tested here.

Primary references checked 2026-09-27: [BrowserContext](https://playwright.dev/python/docs/api/class-browsercontext), [APIRequestContext](https://playwright.dev/python/docs/api/class-apirequestcontext), and [Route](https://playwright.dev/python/docs/api/class-route). Claims are mapped to captures or documentation in [evidence.yaml](evidence.yaml).
