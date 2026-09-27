# Puppeteer localStorage: measured results

Tested 2026-09-27 with Node 22.20.0, Puppeteer 25.12.0 and its bundled Chrome 154.0.8037.57 on macOS 26.6.2 arm64 (Darwin 25.6.0). The local launch retained Chrome's sandbox. Firefox was not tested.

## Denominators and results

- **36 extraction observations** = 12 cases × three rounds. Ten cases use browser DOM extraction; two use a direct Node HTTP request.
- **12 diagnostic observations** = four diagnostics × three rounds.
- **48 checks passed out of 48**. A deliberate wrong-state control passes when it produces the independently specified USD dataset.
- Four expected EUR tuples per observation give **144 repeated record opportunities**, with **84 matching tuple observations**. There are only four unique SKUs.
- **21 extractions matched all four EUR tuples**; **15 matched none**. The latter 15 also matched their independently specified four-record USD control dataset.
- Every extraction observation had four rows and a captured target HTTP 200 status. The three late-write/stale-DOM observations reused the original response and made **zero new catalog requests**. Status observations must not be mistaken for 36 newly sent HTTP requests.

The per-operation counters total **33 catalog requests** across primary observations: 11 per round. They exclude the separately run quickstart. The quickstart and development/unit tests are also excluded from the primary extraction/check denominators.

## Extraction matrix

Each row below has three observations. “EUR match” compares full SKU/currency/price tuples, not status or row count.

| Case | Stored region at observation | Region in rendered/received records | EUR match | New catalog requests |
|---|---|---|---:|---:|
| Fresh page | absent | US | 0/4 | 1 |
| Pre-app initializer | EU | EU | 4/4 | 1 |
| Late `evaluate` write, stale DOM | EU | US | 0/4 | 0 |
| Reload after late write | EU | EU | 4/4 | 1 |
| Snapshot into fresh BrowserContext | EU | EU | 4/4 | 1 |
| New same-origin page in same context | EU | EU | 4/4 | 1 |
| New isolated context | absent | US | 0/4 | 1 |
| Second-port origin, initializer guarded | absent | US | 0/4 | 1 |
| Return to original origin, initializer still installed | EU | EU | 4/4 | 1 |
| `/catalog?region=EU`, fresh context | absent | EU | 4/4 | 1 |
| Direct `/api/catalog?region=EU`, no browser | not applicable | EU | 4/4 | 1 |
| Direct `/api/catalog`, no query | not applicable | US | 0/4 | 1 |

The fixture page chooses an explicit URL region first, then `localStorage.region`, then US. It reads that value once and sends it to `/api/catalog`. The page has no storage-event rerender handler. Consequently, a successful late `setItem('region', 'EU')` can coexist with four old USD DOM rows until reload. The captured storage value, startup source, response region and DOM rows show those separate stages.

The snapshot helper stores only an exact origin and string entries, validates before installation, and restores into a new context while both loopback servers remain running. It does not promise that an origin's state transfers to a different scheme, host or port. The new same-context page has no initializer of its own and reads the shared EU value. The second context starts empty.

The guarded initializer remains installed on the page used for the second-origin and return cases. The second-port page stays empty; returning runs the initializer again. The return observation therefore does not isolate persistence from reapplication. The helper writes unconditionally on every matching new document, which can overwrite a later preference change until the initializer is removed.

## Independent record oracle

Server values are computed from a separate synthetic base-price table. The desired oracle independently hard-codes EUR tuples: `SKU-101/8.10`, `SKU-202/16.20`, `SKU-303/24.30`, `SKU-404/32.40`. The USD control oracle separately hard-codes `SKU-101/9.00`, `SKU-202/18.00`, `SKU-303/27.00`, `SKU-404/36.00`.

Multiset matching caps each SKU/currency/price tuple at its expected multiplicity. Four copies of one correct tuple score one desired match; a fifth extra row invalidates an otherwise complete result. Controls require an exact USD multiset, so corrupting a USD price cannot pass merely because the output still has zero EUR matches.

## Separate diagnostics

All four diagnostics passed in all three rounds:

1. **Blank-page boundary.** Writing localStorage on the new page at `about:blank` returned `SecurityError`. After navigation to the owned HTTP origin, writing and reading the region returned `EU`. No browser-security disabling workaround was used.
2. **Storage event.** Two pages in one context navigated to the same owned origin. The writer set `probe`; the other page received one event and wrote an `ack` key. When the writer received that acknowledgement, its own `probe` event count was zero and the other page's was one. The event recorded `oldValue: null`, the synthetic new value, and `storageArea === localStorage`. A five-second rejection deadline bounds a missing acknowledgement; there is no arbitrary sleep before reading counts. The conclusion is bounded by that acknowledgement, not an infinite observation window.
3. **Node/browser function boundary.** Calling the lexical Node-side `nodeOnlyHelper` inside `page.evaluate` produced `ReferenceError`. Computing a string in Node first and passing it as an evaluation argument stored and returned that exact string. This tests scope transport, not encryption or security efficacy.
4. **JSON argument transport.** Quotes, a backslash, newline, Unicode and script-like text round-tripped through an argument, `JSON.stringify`, localStorage and `JSON.parse`. The text remained data and the page's sentinel stayed false. This one input is a regression probe, not a universal security guarantee.

## Verification and corrections during development

The complete Node test suite passed **24/24** tests. Boundary tests cover tuple multiplicity, snapshot origin/shape/string validation, the direct-query fixture, full capture denominators, duplicate/missing case coverage, three consecutive rounds, altered desired and wrong-state records, diagnostic contradictions, response reuse, and origin mislabeling. Real capture records are re-evaluated by the summary builder; stored scores and headline totals are never sufficient by themselves.

`expected_output/development-red-checks.json` records observed failing development tests: the first oracle/snapshot implementation, the initial summary stub, and the USD-control corruption regression raised during review. They were corrected before the final captures. These are test-development results, not failed browser observations or production defects. There were no failed local browser matrix runs to archive. The initial Linux CI launch failed before the quickstart could run because the hosted Ubuntu runner had no usable Chrome sandbox ([failed run](https://github.com/ScrapingAnt/scrapingant-examples/actions/runs/36337887132)). The workflow now explicitly opts this local-fixture packet out of the sandbox on that CI runner only; the local capture remains sandboxed. The corrected CI result is recorded separately in verification.json.

A clean `npm ci --offline` using the previously downloaded dependency cache succeeded against `package-lock.json`, then the full `./run.sh` completed with its real Chrome run. `comparison.json` is regenerated from `expected_output/chrome.json`. The README lists reproducible commands, and `verification.json` binds source, lock and capture bytes with SHA-256.

## Limits and product connection

The URL-selected rendered catalog and standalone JSON query demonstrate this fixture's explicit application contract. The query-selected browser page has empty localStorage and renders the same four EUR records. Neither proves that another target exposes the same contract, that arbitrary localStorage can become cookies, or that a retrieval service performed these calls. No external service was tested and no API credits were used.

No performance percentage, production reliability estimate, authentication portability, quota guarantee, cryptographic protection, browser profile restart, cross-browser consistency, cookie transfer, sessionStorage or IndexedDB behavior is claimed. The measurements are one Chrome version, one machine, two loopback HTTP origins and three repetitions of a deterministic synthetic application.
