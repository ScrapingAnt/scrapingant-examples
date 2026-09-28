# Captured Puppeteer selection and text results

Tested 2026-09-28 with Node 22.20.0, Puppeteer 25.12.0, Chrome 154.0.8037.57, html-to-text 9.0.5, Darwin 25.6.0 arm64. Chrome's sandbox was enabled. All fixture HTTP navigation and raw HTML retrieval statuses were 200.

The primary matrix has **63/63 declared-outcome checks**: 39 extraction observations (13 cases × 3 rounds), nine API/boundary diagnostics (3 × 3), and 15 text diagnostics (5 × 3). A separate **31/31 boundary tests** passed. Complete quickstarts are separate from these totals. `comparison.json` is recomputed from `expected_output/chrome.json`.

## Element finding and records

Every table row below was observed three times.

| Case | Recorded result | Consequence |
|---|---|---|
| Global `$` | First match is the promotional DECOY record | First matching element is not necessarily a product |
| Global `$$` | DECOY plus A101, B202, C303 | More matches do not repair an overly broad selector |
| Scoped CSS `$$eval` | Three exact catalogue records | Scope repeated records before projecting fields |
| Scoped ElementHandle `$$` | Same three exact records | Querying from a parent handle works; dispose handles |
| `::-p-xpath(...)` | Same three exact records | Current XPath selector form works on this fixture |
| `::-p-text(...)` | B202 via its matching title's closest card | Text selection can identify one record; scope the lookup |
| Scoped `$eval` | A101 only | `$eval` applies to the first matching element |
| Presence-only wait | Three rows with empty title/price fields | A node's presence does not establish populated data |
| Populated-field wait | Three exact catalogue records | Wait for the actual fields that extraction needs |
| Old handle after replacement | Original A101 title; `isConnected=false` | A detached handle can expose stale data in this case |
| Fresh query after replacement | Revised A101 title plus B202/C303 | Re-query the current document after replacement |
| Open shadow selector | SHADOW record | Explicit shadow traversal reaches the open root |
| `contentFrame()` query | FRAME record | Query inside the correct frame document |

Four full-catalogue methods matched the original three-record oracle in each round, giving **12 exact full-catalogue observations out of the 39 extraction observations**. The other observations intentionally target a single record, a decoy, unpopulated fields, changed data or a separate document/root. This denominator is not a success-rate comparison.

The literal catalogue oracle contains SKU, title, currency, decimal price string and relative href. It rejects missing, duplicate, extra, reordered or malformed records and any changed required field. Prices are preserved as strings; no locale parsing or currency conversion is tested.

API diagnostics established `$` → `null`, `$$` → `[]`, `$eval` → an Error naming the missing selector, and `$$eval` with the tested mapping callback → `[]`. A missing optional attribute returned `null`; `getAttribute('href')` retained `/p/b202`, while the DOM `href` property was absolute with that same path. Main-document CSS queries under the shadow host or iframe did not cross either boundary.

## Whole-page text

Each observation records the complete returned text. The comparisons assert these exact declared sentinels rather than platform-sensitive whitespace:

| Method | Visible sentinel | CSS-hidden sentinel | Script sentinel | Style sentinel | Dynamically populated catalogue title |
|---|---|---|---|---|---|
| `body.innerText` | yes | no | no | no | yes |
| `body.textContent` | yes | yes | yes | yes | yes |
| Browser Selection over `Range.selectNodeContents(body)` | yes | no | no | no | yes |
| html-to-text on raw HTTP HTML | yes | yes | no | no | no |
| html-to-text on rendered HTML serialization | yes | yes | no | no | yes |

The raw HTTP body contains placeholders and a script; html-to-text does not execute the script, so it cannot produce the populated title from that response. Serializing the rendered page makes that title available to the converter, but CSS-hidden content still appears in this conversion. `textContent` includes script/style source text and can therefore include product strings from code as well as the rendered records. Flattened text does not preserve the catalogue's record relationships.

Selection here is a programmatic DOM Range operation, not Ctrl+A or clipboard copying. This capture gives no evidence that it recovers content missing because of Bing or other display optimizations. It also does not establish behavior for lazy content that has never entered the DOM.

## Limits and provenance

These are synthetic, handshake-controlled observations on one Chrome build and host, with three repetitions. There are no timing/speed measurements, production targets, paid requests, cross-origin iframe cases or closed shadow roots. The old-handle result concerns same-document node replacement, not navigation or every operation on a detached node.

The fixture's population gate deliberately separates presence from readiness without arbitrary sleeps. Quickstarts start their own local server and always close browser/server resources. Reruns go to ignored output directories, and concurrent full runs are locked.

Source and output hashes are frozen in `verification.json`; tested source binding, independent rerun and passing Linux CI are recorded in `evidence.yaml`. Earlier test-first, dependency/network, port-permission, version-introspection and test-authoring failures are retained in the separate development files and excluded from final denominators. ScrapingAnt claims must cite the shared product packet, not this local capture.
