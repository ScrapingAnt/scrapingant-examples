# Playwright locator evidence report

Tested 2026-09-28 on a self-authored loopback catalog. This report separates observed extraction/control outcomes, diagnostics, offline regression tests, and historical failed attempts.

## Environment and procedure

Python 3.12.10; Playwright 1.63.0; Chromium 153.0.8010.12; Firefox 155.0; macOS 26.6.2 arm64. Installed Python dependencies are captured in `expected_output/dependencies.txt` and pinned in `requirements-lock.txt`.

Each browser ran three rounds. Each extraction/diagnostic case used a fresh page/context, so a prior case's replacements did not leak into another case. The fixture contains an out-of-scope sponsored record, a temporary loading record, three intended catalog records, a same-origin frame record, and an open-shadow record. A controlled gate holds the catalog in its loading state for the eager-count control. Other cases await the application's ready state, non-busy attribute, and expected count before extraction.

## Final denominators

| Category | Denominator | Acceptance |
|---|---:|---|
| Extraction and selection cases | 12 cases × 3 rounds × 2 browsers = 72 observations | Exact predeclared outcomes, including intentionally wrong selections |
| Separate diagnostics | 4 cases × 3 rounds × 2 browsers = 24 observations | Exact predeclared method/error outputs |
| Offline regression tests | 25 test methods | No failures/errors in final recorded run |
| Quickstart | 1 Chromium invocation | Three literal expected records |

The strict summary reports 96 accepted observations and zero mismatches. These are fixture checks, not 96 successful real-site extractions. Historical unsuccessful attempts are preserved under `exploratory/` and are excluded from these final-run denominators. No request timing or speed comparison was measured.

## Extraction cases

| Case | Observed result in each browser/round |
|---|---|
| `strict_duplicate` | Singular read raised strictness error; matched SKUs were AD-000, K-101, M-202, T-303. |
| `first_masks_decoy` | `.first` returned AD-000 / Sponsored kettle / USD / 999.00 / /ads/kettle. |
| `eager_count_all` | Loading state; count and `all()` length were one; extracted PENDING / Loading catalog / XXX / 0.00 / /pending. |
| `scoped_records` | Intended three full catalog records. |
| `locator_reresolution` | Reused locator read archived title before replacement and Copper Kettle afterward; DOM node identity differed; final records matched. |
| `evaluate_all` | One browser-side projection returned the intended three records. |
| `role_records` | Named catalog list and listitem roles returned the intended three records. |
| `text_exact` | Relative exact-text filter returned the full M-202 record; ancestor-prefixed wrong filter returned no SKUs. |
| `css_attribute` | Explicit featured attribute returned the full K-101 record. |
| `xpath_records` | Scoped XPath returned the intended three light-DOM catalog records. |
| `frame_scope` | Explicit frame locator returned F-404 / Frame spoon / USD / 3.25 / /products/spoon. Main-document scope returned the four light-DOM SKUs. |
| `shadow_scope` | Playwright CSS locator returned S-505 / Shadow strainer / EUR / 6.50 / /products/strainer. Raw document `querySelectorAll` returned four light-DOM SKUs; scoped XPath returned no shadow SKUs. |

## Diagnostics

The missing selector produced `TimeoutError` with a 150ms configured operation timeout; elapsed time was not benchmarked. The visible title read was `Tea & Honey`, while `text_content()` included the hidden descendant (`Tea & HoneyHIDDEN`). The raw href was relative and its DOM property was resolved against the local origin; capture substitutes `{origin}` for the random port. A present optional badge was `featured`; a missing attribute was JSON null.

Role lookup excluded the hidden button by default and included it when requested. Text lookup normalized the whitespace example. CSS and XPath both selected the two `.offer` buttons, including the hidden one. This demonstrates why locator families should not be presented as interchangeable string syntax.

## Integrity and limitations

`summarize.py` rejects absent/duplicated case-round pairs, unexpected cases, missing browser captures, schema changes, inconsistent runtimes, altered record tuples, and wrong diagnostic values. It recomputes results and ignores no supplied pass flag: extra row fields are rejected. Record validation requires exact fields, nonempty strings, SKU uniqueness, formatted decimal price strings, and the independent ordered oracle.

`manifest.json` hashes the source and artifact inventory; `integrity.py` rejects changed/missing files, inventory changes, escaping paths, and symlink artifacts. The manifest is an integrity aid, not a signature. Source commit binding and Linux CI are pending, and independent rerun/review remains required before publication.

Only Chromium and Firefox in the captured macOS environment were measured. The frame is same-origin, the shadow root is open, and the data is finite and deliberately controlled. No WebKit, closed shadow roots, cross-origin frame access, virtualized/infinite lists, authentication, anti-bot behavior, remote API, or production site was tested. The ready marker is meaningful because this fixture defines it; adapt readiness to the actual application's contract. `all()` and raw browser DOM queries must not be described as automatic dataset-completeness checks.

The first exploratory text-filter bug and initial sandbox failure remain in the packet. No captured output was handwritten. See `README.md` for runnable commands and official API references. AI assistance was used to prepare code and documentation; this report does not assert completed human review.
