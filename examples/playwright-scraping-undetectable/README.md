# Playwright stealth: local fixtures and dated detector evidence

Five approaches plus plain Chrome/Firefox controls, supporting the existing article at https://scrapingant.com/blog/playwright-scraping-undetectable. No API key or proxy is required.

## What each run means

- `run.sh` launches the three Python Chromium adapters against a self-authored local file. It validates fixture execution and records properties; it does not promise that a public detector passes.
- `run.sh --all` adds Node stealth, Rebrowser, plain Firefox and Camoufox. All seven were run before the article PR was created.
- `diagnostics/2026-09-22/` preserves the earlier public comparison: 28 valid BrowserScan observations, 14 Sannysoft observations, raw DOM, screenshots, pinned dependencies, invalid harness pilots, three separate screenshot-layout visits and independent methodology review.
- Public-suite results used Chrome 153.0.8010.53. The later article fixture run found installed Chrome 154.0.8037.57. The fixture outputs do not update or revalidate the earlier Chrome 153 detector table. Firefox control was 153.0; Camoufox was 152.0.4-beta.30 in both phases.

## Install and run the article's Chrome fixture

Prerequisites for the complete recorded walkthrough: macOS, Python 3.12 (shown as `python3.12` below), installed Google Chrome, and a POSIX shell. Full mode also needs Node 22. Measurements were made on macOS 26.6.2 arm64, Python 3.12.11 and Node 22.20.0. Windows commands and public-suite results on other operating systems were not tested.

From this directory:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
BROWSER_CHANNEL=chrome ./run.sh
```

The commands write to `expected_output/`. To preserve recorded output while rerunning, set `OUTPUT_DIR=generated/latest`. Every process/pipeline failure makes `run.sh` exit nonzero. Results describe this run's actual browser version; installed Chrome can update independently of the Python packages.

The local fixture runs its own inline script and puts JSON in `#result`. `common.py`/`common.cjs` read that DOM text, not `navigator` from a potentially isolated automation evaluation world. No scraping target or public fingerprinting page is contacted by these fixture scripts. `navigator.webdriver` alone is not a bot-detection verdict. The fixture uses a file URL, not an HTTPS origin.

## Individual approaches

Use the activated primary environment and installed Chrome for these exact commands:

```bash
BROWSER_CHANNEL=chrome python 01_playwright.py
BROWSER_CHANNEL=chrome python 02_patchright.py
BROWSER_CHANNEL=chrome python 03_python_stealth.py
```

Each Python file imports the shared helper from this packet; copy the packet, not a single file in isolation. `02_patchright.py` uses Patchright's `sync_playwright`; `03_python_stealth.py` uses `Stealth().use_sync(sync_playwright())`. The helpers launch headless and close their owned browser even on failure.

For the two Node integrations:

```bash
npm ci --ignore-scripts
BROWSER_CHANNEL=chrome node 04_extra_stealth.cjs
BROWSER_CHANNEL=chrome node 05_rebrowser.cjs
```

The lockfile pins playwright-extra 4.3.6, puppeteer-extra-plugin-stealth 2.11.2, Playwright 1.63.0 and rebrowser-playwright 1.52.0. Rebrowser with the installed newer Chrome is a tested combination, not a claim of general driver compatibility.

Camoufox 0.5.6 requires Playwright <1.63, so use a separate environment. The supplied full dependency freeze includes macOS-only PyObjC packages; these commands reproduce macOS, not Linux or Windows:

```bash
python3.12 -m venv .venv-camoufox
.venv-camoufox/bin/python -m pip install -r requirements-camoufox.txt
.venv-camoufox/bin/python -m camoufox fetch official/152.0.4-beta.30
.venv-camoufox/bin/python -m playwright install firefox
.venv-camoufox/bin/python 06_firefox.py
.venv-camoufox/bin/python 07_camoufox.py
```

Camoufox's browser build is explicitly pinned and the script constrains fingerprint OS to the host OS. Other fingerprint settings and default addons remain package defaults. The captured result is macOS-specific; generated fingerprints can vary between launches. Firefox control and Camoufox use different builds.

With all dependencies installed, reproduce the entire local fixture set:

```bash
BROWSER_CHANNEL=chrome CAMOUFOX_PYTHON=.venv-camoufox/bin/python ./run.sh --all
```

## Default CI mode

The repository workflow installs `requirements.txt` and Playwright's bundled Chromium, then runs `./run.sh` without `BROWSER_CHANNEL`. This tests only the three Python adapters on the installed bundled browser, not the installed-Chrome detector comparison. No public detector is a CI pass/fail gate. No secret or authenticated API call is used.

For that same local mode:

```bash
python -m playwright install chromium
OUTPUT_DIR=generated/bundled ./run.sh
```

The Node and Firefox scripts are intentionally excluded from the default monthly job; they are covered by the recorded full local run, not by that job. Node's older Rebrowser browser dependency is another reason not to treat arbitrary bundled-browser combinations as interchangeable.

## Reproduce or inspect the public comparison

See `diagnostics/2026-09-22/README.md` for the exact public-run configuration and `report.md` for conclusions. Its matrix takes two BrowserScan samples per approach/mode and one Sannysoft sample, with fresh contexts, six-/ten-second snapshots and screenshots. Use a new dated copy when rerunning; its orchestrator refuses to overwrite recorded run keys. The original installed Chrome version cannot be recreated by merely reinstalling today's Chrome; supply/record the actual binary available to you and do not relabel the old results.

Validate the retained evidence and regenerate the display table without contacting a public site:

```bash
python diagnostics/2026-09-22/scripts/summarize.py --require-complete
python build_detector_table.py
```

`expected_output/browserscan-table.txt` is derived from those captures. Sannysoft's Chrome-specific checks are not a fair score across Firefox and Chromium. Neither a Normal verdict nor an empty failed-check list demonstrates target-site access, CAPTCHA success or an undetectable browser.

## Failure handling

- Missing Chromium executable: install the matched Playwright browser for default mode, or install Google Chrome when explicitly choosing `BROWSER_CHANNEL=chrome`.
- Camoufox dependency conflict: use its separate pinned environment; do not downgrade the primary Playwright installation.
- Missing helper/fixture/module: run from the complete packet and install its requirements/lockfile.
- A public navigation timeout, unfamiliar detector schema or missing screenshot is an error, never a pass. Keep failed attempts and rerun as a separately dated observation.
- A detected browser is an observation. Do not change the browser flags until it passes and then present that as the original default configuration.

Registry releases, official repository URLs/access dates and inspection SHAs are retained in the diagnostic packet. Exact-source commits for package builds are not inferred from repository heads. The evidence manifest lists the run environments and article claims.
