# Puppeteer element and text extraction evidence

This local-only packet supports two distinct articles: `puppeteer-find-elements` (selecting records) and `puppeteer-get-all-text` (choosing a whole-page text method). It starts a self-authored HTTP fixture on an ephemeral loopback port. It requires no API key and makes no paid requests.

## Run

Node 22 is required (captured with 22.20.0). Install the pinned dependency lock and the Chrome version selected by Puppeteer:

```sh
npm ci
./run.sh
node verify.mjs
```

Puppeteer 25.12.0 and html-to-text 9.0.5 are pinned in `package.json` and `package-lock.json`. If a cached Puppeteer browser is already installed, set `PUPPETEER_CACHE_DIR` to that cache. `run.sh` writes ignored `run_output/`; committed `expected_output/` is the recorded baseline. `OUTPUT_DIR` optionally selects another rerun-output directory. A directory lock prevents concurrent runs. Browser contexts, browser processes and the local HTTP server are closed in `finally` blocks.

The Chrome browser sandbox stays enabled by default. Only a CI environment that cannot provide a usable Chrome sandbox may explicitly set both `CI=true` and `PUPPETEER_NO_SANDBOX=1`; the capture records that choice. This packet does not automatically disable the sandbox.

## Complete quickstarts

```sh
node quickstart.mjs
node text-quickstart.mjs
```

`quickstart.mjs` starts the local fixture, launches Chrome, navigates, releases the fixture's population handshake, waits for all three populated titles/prices, projects JSON from scoped cards, validates the independent oracle, prints the result and closes resources. The application handshake is a test mechanism; a normal website loads its own data. Its saved output is `expected_output/quickstart.json`.

`text-quickstart.mjs` compares `body.innerText`, `body.textContent`, browser Selection over a DOM Range, HTML-to-text on an actual HTTP response, and HTML-to-text on serialized rendered HTML. Its saved output is `expected_output/text-quickstart.json`. Range selection performs no keyboard or clipboard action, and the snippet clears the selection after reading it. Real applications may need to preserve a user's existing selection.

## What the controlled fixture establishes

The catalogue contains three records, a preceding promotional decoy, a missing optional attribute, hidden text, script/style sentinels, a gated initially empty catalogue, a replaceable card, one open shadow root and one same-origin iframe. `oracle.mjs` supplies literal expected records independently of the HTML construction code.

Each of three fresh browser contexts runs 13 extraction observations, three API/boundary diagnostics and five text diagnostics. The 63 checks compare declared outcomes, including intentionally incomplete or incorrect selections. These are not 63 production scraping successes. Quickstarts and 31 boundary tests have separate denominators.

`summarize.mjs` independently rescans every raw record and text sentinel, checks the exact case/round inventory, HTTP statuses, handle attachment, missing API outcomes, metadata shape and saved totals. It rejects stale success flags or changed data. `test/` includes record/schema rejection and capture-tampering regressions. `verify.mjs` checks frozen source/artifact SHA-256 hashes and recomputes `comparison.json`.

## Files and evidence boundaries

- `fixtures/catalog.html`, `fixtures/frame.html`: local application and frame.
- `matrix.mjs`: capture, three Chrome rounds.
- `oracle.mjs`: independent literal records and explicit negative/text expectations.
- `browser.mjs`: launch, readiness and browser-context projections.
- `expected_output/chrome.json`: all raw observations and complete diagnostic text.
- `comparison.json`, `report.md`: recomputed results and interpretation.
- `expected_output/development-red-checks.json`, `expected_output/development-failures.json`: initial test-first failure and exploratory failures retained separately from final observations.
- `verification.json`: immutable source/artifact hashes; source/artifact snapshot binding; final CI and review provenance is recorded in `evidence.yaml`.

The shared `javascript-dom-extraction` packet owns live ScrapingAnt `js_snippet`/HTML-marker evidence. This local packet does not establish an API capability, cost or response guarantee.

## Primary references

Checked 2026-09-28:

- [Puppeteer page interactions and current CSS/text/XPath/shadow selector forms](https://pptr.dev/guides/page-interactions).
- [Puppeteer Page.$$eval](https://pptr.dev/api/puppeteer.page.__eval).
- [MDN innerText](https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement/innerText).
- [MDN textContent](https://developer.mozilla.org/en-US/docs/Web/API/Node/textContent).
- [MDN Range.selectNodeContents](https://developer.mozilla.org/en-US/docs/Web/API/Range/selectNodeContents).

No Bing experiment, speed comparison, generic display-optimization workaround, cross-origin-frame access or closed-shadow-root result is claimed. The fixture proves only the captured APIs, records and declared text sentinels on the reported Chrome build.

## Publication verification

Independent local rerun and Linux source CI passed before the evidence pull request was opened. [Linux run](https://github.com/ScrapingAnt/scrapingant-examples/actions/runs/36403589363). The immutable tested source is recorded in `evidence.yaml`; later changes bind metadata and artifact hashes without changing the measured extraction logic. The default command makes no paid API requests.
