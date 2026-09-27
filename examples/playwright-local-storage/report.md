# Playwright localStorage: captured mechanism report

The final local run on 2026-09-27 passed all 96 predeclared checks across Chromium 153.0.8010.12 and Firefox 155.0. There were 12 extraction cases and four diagnostics per round, three rounds per browser. [comparison.json](comparison.json) is recomputed from [Chromium](expected_output/chromium.json) and [Firefox](expected_output/firefox.json) captures.

All 72 extraction observations returned HTTP 200 and four rows. Only 36/72 matched the four intended EU records, or 144/288 repeated record opportunities. These totals intentionally combine correct-state cases and wrong-state controls. They are not a production success rate or a comparison of browser reliability. Each table row below represents six observations, three in each browser, all with the same result.

| Case | Stored region when captured | API query | Matching EU tuples | Observed behavior |
|---|---|---|---:|---|
| `early_missing_only_seed` | eu | eu | 4/4 | Exact-origin initializer ran before startup read |
| `late_write_without_reload` | eu | us | 0/4 | DOM reread after the write still contained US records |
| `late_write_then_reload` | eu | eu | 4/4 | Reload made startup read the updated preference |
| `fresh_isolated_context` | absent | us | 0/4 | A fresh context did not inherit the source context's preference |
| `storage_state_restore` | eu | eu | 4/4 | Explicit same-origin snapshot restoration populated the new context |
| `same_context_new_page` | eu | eu | 4/4 | A new page shared the source context's same-origin localStorage without an initializer |
| `changed_port_state_miss` | absent | us | 0/4 | Restoring a snapshot for another port did not populate this origin |
| `wrong_origin_initializer` | absent | us | 0/4 | The exact-origin guard skipped the page |
| `missing_only_preserves_change` | us | us | 0/4 | The initializer preserved an intentional change from eu to us on reload |
| `unconditional_overwrites_change` | eu | eu | 4/4 | An unconditional initializer replaced that change on reload |
| `query_only_without_storage` | absent | eu | 4/4 | Page URL `/?region=eu` selected the desired rendered table without storage |
| `query_missing_without_storage` | absent | us | 0/4 | Omitting the selector from a fresh page selected the fixture default |

The zero in the missing-only row is correct behavior for preserving the changed preference. The unconditional row's four matches do not make unconditional initialization appropriate when later user changes must survive navigation. Success is defined by the application's intended behavior, not by one global number.

The page owns the storage-to-request translation. In [fixtures/index.html](fixtures/index.html), startup checks the URL selector, then localStorage, then the default; `fetch` explicitly puts the selected region into the API query. The captures store actual page and response URLs, response status, independently extracted DOM records, API records and the current storage value. LocalStorage is not itself an HTTP request field.

The four diagnostics each passed 6/6 observations (24/24 in total):

- `json_argument_round_trip`: quotes, a backslash, a newline and closing-script text survived argument passing, JSON string storage, and parsing. The stored value had JavaScript type `string`.
- `storage_crud`: read-missing, write, update, remove and clear returned the expected actual values and key counts in an isolated fixture context.
- `session_storage_not_restored`: localStorage was present in a new same-context page and in a fresh context restored from `storage_state`; the synthetic sessionStorage value was absent in both. The new page had no opener, so this does not test opener-copy behavior.
- `storage_event_other_page`: one same-origin sibling page received the localStorage event; the writing page recorded no event. Both pages read the changed value.

The independent literal oracle caps matching tuples at their allowed multiplicity. Exact equality fails on duplicate, missing or extra rows. Negative controls are checked against a separate literal US list, rather than merely accepting any zero-match output. Fifteen offline tests passed, covering this oracle, fixture query boundaries, initializer inputs, complete browser/round/case validation, corrupt scores/flags/URLs, and diagnostic tampering. Their count is separate from browser observations.

The complete quickstart matched four EU tuples; it is excluded from primary counts. The exploratory [sandbox failure](expected_output/exploratory/sandbox-loopback-denied.json) records an actual `PermissionError` before any browser cases ran. The final matrices ran with local server/browser execution permitted. This environmental failure is preserved and excluded rather than counted as an extraction failure.

The URL-selected rendered table establishes only that this fixture exposes a storage-free URL contract. ScrapingAnt documents [browser-rendered HTML retrieval](https://docs.scrapingant.com/headless-browser), but this fixture was never sent to ScrapingAnt and no product efficacy, authentication transfer or localStorage-operation claim follows. ScrapingAnt does not support localStorage operations. Browser automation remains appropriate when that operation is actually required.

Limitations: the three repeats share a deterministic fixture and one Darwin arm64 host; Firefox coverage is local and the default CI runner uses Chromium. This is not a timing benchmark, production reliability estimate, real-login test, cross-browser state migration or browser-restart persistence test. Different port origins are exercised, but HTTPS transitions and storage partitioning are not. SessionStorage's synthetic non-restoration is tested; IndexedDB, OPFS, passkeys, quota and browser storage-policy errors are outside scope. Versions, hashes, source revision and review/CI status belong to [evidence.yaml](evidence.yaml) and [verification.json](verification.json); pending publication checks are not described as complete.
