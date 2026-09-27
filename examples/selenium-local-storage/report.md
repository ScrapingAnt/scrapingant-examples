# Selenium localStorage evidence report

Tested 2026-09-27 with Python 3.12.10, Selenium 4.49.0, and macOS 26.6.2 arm64. Chrome 154.0.8037.57 used ChromeDriver 154.0.8037.57; Firefox 156.0 used GeckoDriver 0.37.1. The version values come from the actual WebDriver capabilities in the captures, not from a latest-release assumption. Dependencies are pinned in `requirements-lock.txt`.

The final capture command, after activating the locked environment and selecting the installed Firefox binary/driver with `FIREFOX_BINARY` and `GECKODRIVER`, was:

```bash
OUTPUT_DIR=expected_output ./run.sh --all-browsers
```

The interpreter was selected with `PYTHON_BIN`. The public command uses portable variable names; machine-specific binary locations are not part of the packet. `SELENIUM_NO_SANDBOX` was unset. A normal rerun uses `./run.sh --all-browsers` and writes `run_output/`.

## Observed results

Every browser completed three rounds, with 12 extraction cases and eight diagnostic cases per round. The resulting 120 scenario assertions passed. The 72 extraction observations consist of 60 browser-page observations plus 12 direct HTTP controls. Diagnostics have their own denominator: 48 observations. The quickstart and 22 regression tests are additional checks, excluded from those denominators.

The target dataset is exactly four tuples: `(SKU-1, EUR, 825)`, `(SKU-2, EUR, 1675)`, `(SKU-3, EUR, 2425)`, and `(SKU-4, EUR, 3350)`. `oracle.py` defines them literally, independently of the fixture's generation code. It also defines a separate literal USD control dataset. Comparisons use full multisets, rejecting missing, duplicate, extra, malformed, wrong-price, or wrong-currency records.

Across the six browser rounds, bootstrap seeding, reload after a late write, an application-triggered asynchronous update, manual restoration, and the URL-selected rendered page each returned 24/24 target records across six observations. The direct query-selected HTTP control also returned 24/24 target records. Empty startup, a late write without reload, a different port, sessionStorage-only state, a fresh driver without restoration, and the direct request with no query each returned 0/24 target records; each matched the independently specified USD control instead.

The late-write observation is particularly useful: storage read `eu` while the last catalog request and DOM still described `us`. Reload caused the fixture to reread storage and explicitly request `region=eu`. The delayed update first captured `{storedRegion: null, region: "us", stage: "scheduled"}`. The wait then required both the new stored value and the full correct records. No elapsed-time comparison is made.

The rendered route `/catalog?region=eu` returned the expected EUR rows in a fresh driver while `localStorage.demo_region` stayed null. The default route in that same fresh driver returned USD rows. This proves the fixture's explicit URL-selection contract. There was no ScrapingAnt call or service handoff test.

## Diagnostic observations

| Diagnostic | Observed in each of six rounds |
|---|---|
| Opaque `data:` document | Access raised JavaScript `SecurityError` |
| `execute_script` arguments | Apostrophe, newline, Cyrillic, Greek, and emoji strings round-tripped exactly |
| Legacy interpolation control | The controlled malformed JavaScript raised `JavascriptException`; its key remained absent |
| JSON values | Python JSON decoding and browser `JSON.parse` agreed on the nested value |
| Selective removal | `demo_region` was absent and `keep_me` remained `retained` |
| Wrong-port restoration | Helper raised `ValueError`; other-origin storage remained empty |
| Async precondition | Preference was absent, dataset was US, and application stage was scheduled |
| Manual restoration contents | Exported and restored snapshots agreed on all three keys and string values |

The snapshot guard validates all entries before mutation and queries `location.origin` in the document where script execution occurs. Unit tests additionally reject changed scheme, hostname, port, selected script-document origin, malformed snapshots, duplicate keys, and non-string values. The browser matrix itself does not exercise embedded frames.

## Integrity and regression checks

`expected_output/tests.txt` records 22 passing tests. They exercise the independent record oracle, argument separation, exact-origin guards, a storage-correct/data-stale wait, the direct HTTP URL guard, and a real loopback request while proxy environment variables point at an unusable endpoint. They also mutate saved captures to test missing rounds/cases, duplicate cases, forged counters, wrong transport/state, malformed rows, false flags, diagnostic contradictions, invalid environment fields, request mismatch, duplicate JSON keys, and nonfinite numbers.

A forced failure regression confirms that completed observations survive in a partial matrix capture while only the exception class is recorded. The strict summary refuses failed or incomplete captures. `summarize.py` rescans every saved record and request event; it does not accept stored `assertion_passed`, row counts, match counts, or totals as sufficient evidence. `verification.json` and `verify_hashes.py` provide a reproducible SHA-256 check of the packet files.

The earlier successful smoke and superseded full runs remain under `exploratory_output/`, explicitly excluded. There were no failed exploratory browser runs. `expected_output/run.log` is the final full command output. The raw browser captures include timestamps and browser/driver versions; their loopback port numbers naturally vary across reruns.

## Limits and interpretation

These are controlled observations of a self-authored catalog on one host. All requests intentionally made by the application and direct-request helper are local. Driver/package provisioning may use network access. No real credentials, account, paid API request, ScrapingAnt credit, speed percentage, or production reliability estimate is involved.

LocalStorage is not a cookie and is not automatically included in HTTP requests. In this fixture JavaScript performs a specific translation into a query. An arbitrary real site's localStorage cannot be assumed to have a URL/cookie equivalent. A fresh WebDriver profile beginning empty does not mean that persistent browser profiles erase localStorage on exit. The export covers only localStorage for one exact origin and replaces that origin's existing localStorage when restored.

The packet does not test real logins, SSO, quotas, encryption, production security, cross-tab storage events, service workers, or persistent browser profiles. MDN's storage-event behavior is documentation context, not a measured diagnostic here. Linux CI and independent publication review remain publishing-stage checks; they are not preclaimed by this local report.
