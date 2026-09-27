# Puppeteer localStorage evidence

A runnable, no-secret experiment about startup timing, origin scope, browser contexts and record extraction. A self-authored loopback application reads `localStorage.region` once at startup and sends an explicit region query to its catalog endpoint. Every product and stored value is synthetic.

## Run

Node 22.12 or newer is required by the pinned Puppeteer package. Captures used Node 22.20.0 and Puppeteer 25.12.0.

```bash
cd examples/puppeteer-local-storage
npm ci
./run.sh
```

Puppeteer's normal install supplies its bundled Chrome. Linux also needs Chrome's system libraries; consult the [official troubleshooting guide](https://pptr.dev/troubleshooting). The default runner retains Chrome's sandbox. On a CI runner that requires an explicit opt-out, the supported override is `CI=true PUPPETEER_NO_SANDBOX=1 ./run.sh`; the runner rejects this opt-out outside an explicitly marked CI run. The local capture used the sandbox and did not need that override.

`PUPPETEER_CACHE_DIR` can select an alternate browser cache. `NODE_BIN` selects Node; `OUTPUT_DIR` changes the output folder. Reruns write to ignored `run_output/`, leaving the committed `expected_output/` captures unchanged. Runtime targets are two temporary HTTP servers bound to `127.0.0.1`; no external site, account, cookie, API key, paid API or storage service is used.

## Quickstart

```bash
node quickstart.mjs run_output/quickstart.json
```

[quickstart.mjs](quickstart.mjs) is complete when run with the adjacent helpers. It installs synthetic state with `evaluateOnNewDocument`, checks the exact origin, saves a JSON snapshot, restores it into a fresh BrowserContext, and extracts four records. It also opens a fresh context at `/catalog?region=EU`: this fixture renders the same four records while localStorage remains empty.

[Captured quickstart output](expected_output/quickstart.json) includes the actual records, statuses, storage values, version metadata and confirmation that the temporary snapshot was removed. The target tuple oracle is independent from the server's pricing code:

| SKU | Currency | Price |
|---|---|---:|
| SKU-101 | EUR | 8.10 |
| SKU-202 | EUR | 16.20 |
| SKU-303 | EUR | 24.30 |
| SKU-404 | EUR | 32.40 |

The snapshot format stores one canonical origin and a list of string key/value pairs. It rejects paths, credentials, duplicate keys, nonstring values and a different intended origin. Values are passed as evaluation arguments, not interpolated into JavaScript source. The initializer writes its entries on every matching document: it can overwrite later preference changes until removed with `page.removeScriptToEvaluateOnNewDocument(identifier)`. It is a small explicit helper, not a complete browser-profile export.

## What is measured

The [report](report.md) and [comparison](comparison.json) cover 12 extraction cases plus four diagnostics, repeated three times in bundled Chrome. Separate scenarios expose late storage writes with stale DOM, reload behavior, state restoration, shared pages, isolated contexts, a second-port origin, URL-selected rendering, and direct JSON queries. Diagnostics cover `about:blank` access, an event acknowledgement between pages, the Node/browser function boundary, and quoted/Unicode JSON transport.

A successful HTTP status or four rows is insufficient. The target oracle requires a complete multiset of four literal EUR tuples. Wrong-state controls must separately match four literal USD tuples; arbitrary nonmatching rows fail. Extra, missing and duplicate records are rejected.

## Reproduce individual steps

```bash
npm test
node test_suite.mjs run_output/test-results.json
node matrix.mjs run_output/chrome.json
node summarize.mjs run_output/chrome.json run_output/comparison.json
```

The summary independently rescans records and expected control datasets, validates each case exactly once in each of three consecutive rounds, checks origin/port/path/transport boundaries, verifies diagnostic outcomes, and rejects contradictory stored scores or headline totals. Tests mutate a committed real capture to exercise those failure paths.

To rebuild from committed captures without launching Chrome:

```bash
node summarize.mjs expected_output/chrome.json run_output/comparison-from-captures.json
cmp comparison.json run_output/comparison-from-captures.json
node verify.mjs --check
```

`verification.json` contains SHA-256 hashes for packet sources, dependency lock, documentation and committed captures. After an intentional reviewed change, regenerate it with `node verify.mjs --write`; ordinary reruns do not rewrite it. Commit metadata is filled after the source commit exists and then the hash manifest must be regenerated.

## Limits and retrieval boundary

This is a deterministic mechanism experiment in Chrome 154.0.8037.57 on macOS 26.6.2 arm64. Firefox was not measured. Three repetitions on one machine do not estimate production reliability or performance. No authentication, browser restart/profile persistence, encryption, storage quota, sessionStorage or IndexedDB claim is tested.

The region query works because this application defines it. Neither localStorage nor arbitrary browser state is automatically converted into a URL, cookie or service parameter. The URL-selected rendered page and direct JSON endpoint are local fixture controls; no retrieval service was called. If a target lacks a reproducible retrieval URL or another supported request contract, browser automation may still be required to establish its state.

The storage-event writer observation ends when it receives the other page's acknowledgement; it is not an indefinite claim that no future event can occur. The return-to-original-origin case keeps the initializer installed, so it cannot distinguish retained state from initializer reapplication.

Primary references, checked 2026-09-27: [evaluateOnNewDocument](https://pptr.dev/api/puppeteer.page.evaluateonnewdocument), [BrowserContext creation](https://pptr.dev/api/puppeteer.browser.createbrowsercontext), [JavaScript execution](https://pptr.dev/guides/javascript-execution), [MDN localStorage](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage), and [MDN storage events](https://developer.mozilla.org/en-US/docs/Web/API/Window/storage_event). Claim mappings are in [evidence.yaml](evidence.yaml).
