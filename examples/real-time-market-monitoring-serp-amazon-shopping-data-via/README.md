# Amazon listing snapshot comparison

Evidence packet for https://scrapingant.com/blog/real-time-market-monitoring-serp-amazon-shopping-data-via

This is a guide component for builders of an Amazon tracker: parse owned Amazon-shaped HTML and compare a bounded listing window without turning incomplete captures into change alerts. It is not a finished tracker, a verified live Amazon scraper, or a Google/Shopping adapter. All ASINs, product names, prices, timestamps and source URLs in the fixtures are synthetic. No third-party page content was copied.

## Run offline

Tested with CPython 3.12.11. There are no third-party dependencies and no installation step. From this directory:

```bash
./run.sh
```

If `python3` is not your intended Python interpreter, set `PYTHON` to its executable. The default run never calls the API, even when a key is present. Every acquisition test supplies a mocked transport. The PR-only workflow uses Python 3.12.11 with no secrets, scheduled jobs or live requests.

Individual commands, also run by the script:

```bash
python3 snapshot.py fixtures/baseline.html fixtures/changed.html
python3 snapshot.py fixtures/baseline.html fixtures/truncated.html
python3 budget.py
python3 verify_captures.py
```

## What the fixture contract means

- The six-card page-one window includes ads. `observed_position` is the index in the captured list, never an organic rank.
- One ASIN appears as both an ad and an organic placement. Records remain separate. `(asin, sponsored_status)` identifies uniquely matchable placements; repeated placements within that same class are preserved and reported as ambiguous instead of arbitrarily paired.
- The owned `Organic` annotation explicitly marks an organic fixture placement. Missing, ambiguous or conflicting placement labels become `unknown`. This is not a real Amazon selector rule.
- Every record retains query, marketplace, currency, observed UTC and source URL. A missing/invalid ASIN is null and makes the snapshot ineligible for comparison. Missing title or price is null, not an empty product or zero price. A price change requires two known prices in the same snapshot currency.
- The annotated envelope's expected count, page, capture status, completion declaration and terminal signal describe this owned bounded window. Duplicate attributes anywhere in the capture, missing/truncated markup, absent or inconsistent signals, wrong count/page and block/error status suppress all changes. Conflicting ASIN or completion attributes cannot override the rejection. Counts can legitimately vary on real pages; a production adapter needs an independently justified window/completion policy, not a fixed universal six-result rule.
- Same query, marketplace, currency, source URL, page and window contract are required, with strictly increasing UTC observations. A currency/source/context change is suppressed, not normalized silently.
- `not_observed_in_window` only describes this captured window. It does not mean a product was delisted or became unavailable. A changed position may reflect observed layout, ads or personalization rather than a market change.

The literal `fixtures/oracle.json` was authored separately from the parser and diff output. `verify_captures.py` checks all three record captures and two diffs, then rejects five deliberate record/provenance mutations. `naive.py` is a labeled, deliberately wrong completeness-blind set-difference demonstration.

## Optional acquisition and the bounded owned transport check

Use an official/approved dataset or a permitted direct request when it supplies the needed fields. If managed retrieval is appropriate, validate your permission, source layout and actual fields before scheduling work. Set `SCRAPINGANT_API_KEY` in your environment; never put it in code, query strings, logs or support messages. Supply your permitted target URL locally:

```bash
python3 acquire.py --url "$PERMITTED_QUERY_URL" --browser true --permitted --max-attempts 1 --max-credits 10 --out local-capture
```

This CLI command is an unexecuted live integration option. `acquire.py` retrieves HTML from `/v2/general`, not structured product JSON, and saves one capture plus local provenance. The key is sent only in the `x-api-key` header. Raw mode requires explicit `--browser false`. Both modes explicitly set datacenter proxy, US proxy country, API timeout 30 seconds and `return_page_source=false`; client transport timeout is 35 seconds. It rejects missing/invalid credit receipts, target status other than 200, non-HTML content, bodies over 2,000,000 bytes and invalid UTF-8. Target content type comes from `Ant-original-header-content-type` when present; it uses the outer `Content-Type` only as a fallback. The general response may lack that outer header. Missing both types is unknown and rejected; an explicitly non-HTML target type cannot be overridden by an outer HTML type. An HTTP 200 HTML capture still has `accepted_snapshot=false`: successful transport is not extraction or coverage validation.

One separate genuine transport check used the unchanged `acquire.fetch_html` function against the existing owned `dynamic-delayed.html` fixture on October 11, 2026, from 21:38:50.623018 to 21:38:51.364459 UTC. Raw mode (`browser=false`), datacenter/US, timeout30 and page-sourcefalse returned API200/target200, 752 bytes and an `Ant-credits-cost` receipt of 1. The raw `<div id="test">Web Scraping is hard</div>` marker was present. Saved response SHA256: `d670add5613e47f7e29d08480a1eec2b2fca04e94e18eba4628fe44e9b124e93`.

The saved body and receipt are in `captures/2026-10-11-owned-raw/`; its metadata pins the tested acquisition source and the byte-matching owned fixture source. The capture is HTML transport evidence for that owned page only. It contains no Amazon records, does not validate an Amazon adapter or complete listing snapshot, and does not execute the acquisition CLI. `expected_output/owned-transport-verification.json` records offline hash/receipt/marker verification. Replay without a key or network:

```bash
python3 - <<'PY'
import hashlib, json
from pathlib import Path
p = Path("captures/2026-10-11-owned-raw")
body = (p / "response.html").read_bytes()
receipt = json.loads((p / "receipt.json").read_text())
assert len(body) == 752
assert hashlib.sha256(body).hexdigest() == "d670add5613e47f7e29d08480a1eec2b2fca04e94e18eba4628fe44e9b124e93"
assert receipt["http_status"] == 200 and receipt["target_status"] == "200"
assert receipt["credit_receipt"] == "1" and receipt["actual_credits"] == 1
assert b'<div id="test">Web Scraping is hard</div>' in body
assert b'<div id="loaded">' not in body
print("Saved owned raw transport verified; no Amazon snapshot accepted.")
PY
```

`--out` must name a new directory whose parent already exists. The CLI reserves that directory and opens both destination files before retrieval, so an existing destination, missing parent or local preflight error causes no provider call. It never overwrites an earlier capture. A later filesystem failure can still prevent saving a response; inspect the local destination before deciding whether to retrieve again.

One page and one attempt are the CLI defaults. The optional two-attempt cap only retries an explicit HTTP 500 after one second, with a reserve for both calls; authentication, quota, validation, concurrency and network-timeout cases stop. A client timeout leaves remote completion unknown. There is no pagination, residential fallback, loop, scheduler or model call. The byte cap applies to saved API HTML, not browser-internal subrequests. The local reserve is planning arithmetic, not a server-enforced spend ceiling; inspect `Ant-credits-cost` receipts locally.

Real Amazon HTML will not contain this packet's annotated envelope and terminal marker. Do not send an arbitrary live capture directly through the owned-fixture adapter or manufacture completeness metadata to make it pass. First build and validate a source adapter against permitted real responses, including ad labels, result ordering, currency, selected marketplace and a defensible completion signal. Actual Amazon source coverage, target success and live charges remain unverified.

## Budget arithmetic

`budget.py` counts query × marketplace × runs per day × days snapshots; multiply by pages per snapshot for initial calls, then by the per-page attempt cap. Its example uses 5 queries, one marketplace, one page, 24 runs/day and 30 days: 3,600 initial calls; at most 7,200 attempts with a two-attempt cap. Documented datacenter costs give 7,200 raw-mode credits or 72,000 rendered-mode credits at that cap. This is a planning scenario, not measured traffic, billing or a forecast. Inspect response receipts for the actual workload. Costs for extraction or another proxy mode need a separate calculation.

Sources checked October 11, 2026:

- [Request/response format](https://docs.scrapingant.com/request-response-format): general endpoint returns HTML.
- [Credit costs](https://docs.scrapingant.com/credits-cost): raw/datacenter 1 credit, rendered/datacenter 10 credits; receipt header.
- [Errors](https://docs.scrapingant.com/errors): status-specific handling; header authentication supported.
- [Current plans](https://scrapingant.com/#pricing) and [signup](https://app.scrapingant.com/signup): choose only after verifying fields, mode and bounded workload.

Public documentation and rendering landing copy disagree on some defaults/timeout descriptions. This packet avoids those assumptions with explicit parameters. It does not assert a universal timeout range or deployment configuration.

## Files and limitations

`snapshot.py` is the parser/diff; `acquire.py` is the acquisition adapter whose raw function was exercised once against an owned page, while its CLI and Amazon integration remain unexecuted; `budget.py` is planning arithmetic; `fixtures/` holds local owned inputs and literal expectations. `captures/` contains the separate dated genuine owned transport. `expected_output/` contains actual offline captures, test results, tamper controls, environment and SHA-256 byte hashes. `requirements.txt` records no third-party dependencies.

49 offline unittest methods passed on October 11, 2026; subcases cover more input variations without pretending to be a target sample. This includes duplicate-attribute rejection, output-destination preflight and source-shaped response-header controls. Three synthetic captures and two synthetic diffs are the comparison denominator. The separate live denominator is one raw request to an owned page, costing one recorded credit. No Amazon target pages, browser sessions, success-rate benchmark, scheduling service, stock/Buy Box/review extraction or price recommendation was tested. Named-author review is pending. This packet alone does not establish that the article should be indexed or that a production tracker is ready.
