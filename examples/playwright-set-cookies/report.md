# Measured results: Playwright cookies and state

Tested 2026-09-27. Three rounds each in bundled Chromium 153.0.8010.12 and Firefox 155.0, using Playwright 1.63.0 / Python 3.12.10 on macOS 26.6.2 arm64. Package versions and timestamps are included in the captures.

## Denominators

- 12 extraction cases × 3 rounds × 2 browsers = **72 extraction observations**.
- Six diagnostics × 3 rounds × 2 browsers = **36 diagnostic observations**.
- Together: **108 checks, 108 passed**. A deliberately wrong-state control passes its check when it produces the predicted wrong records.
- Four literal expected SKU/currency/price tuples per extraction = **288 record opportunities** across repeated observations. These are not 288 unique products.
- **30 observations** matched all four records; **42** matched none. This gives **120 matching record observations**, not a production success rate.
- All **72/72** primary extractions returned HTTP 200 and four rows. Those two signals alone did not distinguish correct records from wrong-state controls.

The independently rescored summary is [comparison.json](comparison.json). Only `expected_output/chromium.json` and `expected_output/firefox.json` enter the primary comparison. The quickstart's two extractions, offline tests and exploratory run are excluded.

## Extraction observations

Every row below has six observations, each with target HTTP 200 and four returned records. “Match” compares complete SKU/currency/price tuples against the literal member/EUR oracle.

| Case | Captured audience / region | Match per observation | Interpretation |
|---|---|---:|---|
| Fresh browser | retail / US | 0/4 | No session or region state |
| Cookie before first navigation | member / EU | 4/4 | Cookie installed at `about:blank`; explicit fixture region initialization accompanies it |
| Server-seeded browser | member / EU | 4/4 | `/seed` sets the cookie and localStorage preference |
| Full storage state restored | member / EU | 4/4 | New context receives cookie and exact-origin localStorage |
| Cookies-only restored | member / US | 0/4 | Cookie preserves membership; omitted region changes currency and prices |
| Shared API, explicit region | member / EU | 4/4 | `context.request` shares cookies; the fixture region is supplied as a query parameter |
| Shared API, no region parameter | member / US | 0/4 | Shared cookies do not execute the page's localStorage-reading JavaScript |
| Isolated API, no handoff | retail / EU | 0/4 | A fresh `playwright.request.new_context()` has its own cookie jar |
| Isolated API with state handoff | member / EU | 4/4 | `storage_state` supplies cookies; an explicit application-specific query supplies the region |
| Other browser context | retail / US | 0/4 | A concurrently open second browser context has separate state |
| API Set-Cookie then browser | retail / EU | 0/4 | `/session/guest` via `context.request` updates the browser jar; region remains EU |
| Wrong cookie path | retail / EU | 0/4 | Cookie scoped to `/admin` is absent from the `/api/catalog` request |

The fixture computes member EUR prices from its own server-side pricing table. The oracle separately hard-codes four expected tuples (`SKU-101/EUR/8.10`, `SKU-202/EUR/16.20`, `SKU-303/EUR/24.30`, `SKU-404/EUR/32.40`). It uses multiset intersection and equality. Four duplicates of one expected row score one match, never four; a fifth duplicate invalidates an otherwise complete extraction.

## Separate diagnostics

All six observations for each diagnostic passed:

- Cookie insertion occurred while the page remained `about:blank`, with no catalog navigation, and the cookie was visible to `context.cookies(origin)`.
- The synthetic session cookie was marked HttpOnly in context inspection and absent from `document.cookie`.
- Changing the other context's cookie to `guest-v1` left the seeded context's cookie at `member-v1`.

For each routing mode, one navigation to a unique diagnostic endpoint was measured using the server's actual HTTP hit counter. There is no catalog extraction in these routing counts:

| Route mode | Observations | Server hits per navigation | Total hits |
|---|---:|---:|---:|
| Normal navigation | 6 | 1 | 6 |
| `route.fetch()` then `route.continue_()` | 6 | 2 | 12 |
| `route.fetch()` then `route.fulfill(response=...)` | 6 | 1 | 6 |

This measures this GET endpoint with the captured versions. It does not prove every interception sequence, redirect chain or browser version has an identical request count. [Playwright's Route reference](https://playwright.dev/python/docs/api/class-route#route-fetch) describes fetching a response for fulfillment; the capture supplies the measured duplicate-request finding.

## Verification and corrections

The boundary suite contains 19 passing tests covering multiset correctness, an exact-origin region adapter, cookie/region server boundaries, summary denominators, and malformed or incomplete capture rejection. `offline_checks.py` also runs a deliberate in-memory naive-membership mutant: the duplicate-row regression test fails as intended. See [expected_output/offline-checks.json](expected_output/offline-checks.json). The initial oracle/adapter tests and eight added capture-validator regressions were observed failing before their implementations were corrected.

Independent review found that the first summary implementation trusted serialized scores. The corrected builder rescans raw records, rejects mismatched score/check metadata, duplicate browser captures, missing/duplicate cases, wrong case classifications and nonconsecutive rounds. Rebuilding the comparison from the corrected primary captures preserved all totals above. Fixture-only urllib reads explicitly ignore ambient HTTP proxies; tests passed with deliberately invalid proxy settings.

An earlier Chromium diagnostic run used a two-argument callback whose optional mode parameter received Playwright's request object. Both labeled interception branches therefore fulfilled the response. That run recorded 51/54 checks passing and is retained at [expected_output/exploratory/chromium-handler-signature-bug.json](expected_output/exploratory/chromium-handler-signature-bug.json). It is excluded from the comparison and cannot establish a fetch/continue request count. The handler was changed to one argument, and both complete browser matrices were rerun successfully. The primary captures additionally record the HttpOnly flag needed to validate that diagnostic independently.

## Limits

This small self-authored catalog isolates browser/API state boundaries. It provides no estimate for a production site's reliability, login portability or anti-bot behavior. Three repetitions per browser share one machine and fixture design. There are no real users, credentials or production cookies.

“Full state” in this report means the full `storage_state()` snapshot used by this fixture, whose relevant state is cookies plus localStorage. It is not a promise to export a whole browser profile. LocalStorage determines a region query only because this application implements that behavior; an API state file alone does not recreate arbitrary JavaScript application logic. The experiment does not exercise sessionStorage, IndexedDB, OPFS, passkeys, MFA, SSO, cross-origin or IP-bound sessions, partitioned cookies, cross-site SameSite behavior, or Secure cookies over HTTPS.

## Publication verification

Executable source: `daa3b8bfe914b160e622be41fbf05ef161f4f2c6`. [Linux CI passed](https://github.com/ScrapingAnt/scrapingant-examples/actions/runs/36334989959) before the evidence pull request was opened: 19 tests and 54/54 designed matrix checks using bundled Chromium. The separately captured and independently rerun local Chromium plus Firefox matrix contains 108/108 checks. See [verification.json](verification.json) for hashes and the exact CI source. No executable code or primary captures changed when this provenance was recorded.
