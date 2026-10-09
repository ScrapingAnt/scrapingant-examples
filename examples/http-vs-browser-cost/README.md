# HTTP vs browser cost: controlled fixture evidence

This packet compares raw HTTP and browser acquisition by exact accepted output and actual API credit receipts. It is a controlled extraction study, not a real-world reliability or anti-bot benchmark. **The owner-approved public-origin run is complete: 80 acquisitions, including 40 ScrapingAnt API attempts and exactly 220 receipted credits.** All four arms are captured. Separate local loopback results are retained; they are not pooled with public-origin timings.

## Reproduce locally, without paid calls

Run from this directory with Python 3.12 on a POSIX system. Direct dependencies are pinned. The caller deadline uses POSIX signals; Windows is not supported by this runner. Browser/package downloads need network access. Fresh Linux hosts may also require Playwright system dependencies; follow the [official browser installation guide](https://playwright.dev/python/docs/browsers#install-system-dependencies). Only the documented macOS environment was captured here.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
./run.sh
```

The default run serves only loopback fixture copies, makes 40 local acquisitions and never reads an API key. It refuses to overwrite a run directory. Use a fresh `--out` path for another run. Raw bodies, every attempt and the computed summary are preserved. Expected contract failures do not make the harness fail: the delayed Requests rows are intentionally invalid extraction results. Regression tests, run integrity failures and budget/receipt failures do exit nonzero.

```bash
python runner.py --out run_output/another-local-run
python verify_capture.py expected_output/local/report.json
```

## Targets and literal contracts

The existing published fixtures belong to `ScrapingAnt/scrapingant-examples`. Repository `fixtures/README.md` documents their GitHub Pages URLs. `expected_output/fixture-check.json` records two HTTP 200 reads and exact source/public SHA-256 equality on October 9, 2026. No new endpoint was published.

| Target | Existing URL | Accepted output |
|---|---|---|
| Static catalog | https://scrapingant.github.io/scrapingant-examples/fixtures/html-tables.html | Exactly three ordered `#prices tbody tr` rows, all four cell values equal independently written literals in `contract.py` |
| Delayed DOM diagnostic | https://scrapingant.github.io/scrapingant-examples/fixtures/dynamic-delayed.html | One exact `#test` text plus one `#loaded` marker |

The static contract comprises product, displayed USD price, units sold and share. The diagnostic's single text sentinel is **not a commercial record**. Keep their summaries separate. Thirty accepted catalog record observations are repeated captures of three unique records. Ten accepted diagnostic observations repeat one sentinel. No blend across these denominators is meaningful.

## Local run recorded October 9

`expected_output/local/report.json` and forty `body-*.html` files are actual captures. `expected_output/summary.json` is offline recomputation; `expected_output/unit-tests.txt` contains the regression output.

| Target | Arm | Valid attempts | Accepted observations | Median all attempts |
|---|---|---:|---:|---:|
| Static | Requests | 10/10 | 30 catalog records | 5.98 ms |
| Static | Playwright | 10/10 | 30 catalog records | 112.53 ms |
| Delayed diagnostic | Requests | 0/10 | 0 sentinels | 1.84 ms; invalid outputs |
| Delayed diagnostic | Playwright | 10/10 | 10 sentinels | 1891.56 ms |

The final source capture overlapped a local blog build; other host activity was not controlled. These loopback timings are illustrative. Earlier runs are preserved under `expected_output/exploratory/` outside the final denominator.

The run used Python 3.12.10, Requests 2.34.2, BeautifulSoup 4.15.0, Playwright 1.62.0 and bundled Chromium 151.0.7922.34 on macOS 26.6.2 arm64. Initial browser launch was 367.09 ms, recorded separately. Browser reuse: one browser, fresh context/page per attempt. Requests reuses its Session. The local server's HTTP/1.0 behavior does not establish persistent-connection performance on production origins. CPU/memory, client geography, host/proxy/labor cash costs and API worker versions were not measured. Timezone is captured metadata, not a geographic measurement.

Ten rounds use seed 607 and shuffle both target order and arm order. Acquisition/readiness budget is 10 seconds; caller wall limit is 15 seconds including parsing/validation. Direct navigation and selector waits share the remaining budget. API worker timeout is 10 seconds; client transit is distinct from worker execution. Requests has connect=5/read=10 plus the same outer wall deadline. Requests/API client redirects and application retries are disabled. Playwright retains normal browser navigation/redirect behavior; these fixed fixtures returned HTTP 200 without redirects in the public checks. No application retry loop is added. Timings include context/page creation but exclude initial browser launch and context cleanup.

## Inspect or plan live reproduction

Read-only fixture inspection makes two direct requests; it never calls ScrapingAnt:

```bash
python runner.py --inspect-public --out run_output/fixture-check
```

The paid command below reproduces the recorded acquisition design. **Each new execution requires its own prior owner-approved budget.** The October 9 run used `run_output/live-approved-20261009`; no pilot, warmup or retry was run. Configure `SCRAPINGANT_API_KEY` securely in the environment; do not put the key in command arguments or committed files:

```bash
python runner.py --live --repeats 10 --approved-credits 220 --out run_output/live
```

It executes two targets × ten rounds × four arms: 80 acquisitions, including exactly 40 API attempts. The approved ceiling and actual receipted total were both 220 credits: raw 1 and rendered 10 per target/round. Two source/public hash checks precede calls. Live acquisitions are separated by at least one second; concurrency is one. No warmups, retry loops, residential proxies, AI/model calls or subscription changes. A one-round wiring pilot instead needs `--repeats 1 --approved-credits 22`; it cannot support comparative latency claims.

API parameters explicitly select datacenter mode. Rendered retrieval uses `browser=true`, `return_page_source=false` and the same page-created readiness selector as Playwright. Raw retrieval uses `browser=false` and no selector. The separate documented two-credit browser/page-source mode is excluded. The key is sent only to the fixed API endpoint in its authentication header, never to target pages. Sessions ignore environment proxies. Only response credit/target-status headers are saved; raw exceptions and prepared request URLs are never printed.

Before each API attempt the runner reserves its documented cost against the remaining approved ceiling. A missing or unexpected receipt stops further work (the expected arm charge, or zero only for an API error status, is allowed) and preserves the partial report for billing reconciliation. Do not rerun a timed-out request blindly: it can have uncertain billing. This client guard does not enforce a provider-side billing cap or reconcile the account ledger. The captured report has every initiated API attempt and its actual receipt. A completed client ledger does not independently reconcile the provider account ledger.

## Public-origin four-arm run recorded October 9

`expected_output/live/report.json` and all 80 raw bodies are the original captures; `expected_output/live-summary.json` is the offline summary. `capture-provenance.json` records the executed command and original local runtime revision `05cbdf3080507b8f3f2d41ad65bb3ddd42b5d587`. The report binds runtime files by SHA-256. The original local revision is retained as execution provenance; this review branch publishes byte-identical runtime files without private planning history. Verify it without an API key or any network request:

```bash
python verify_capture.py expected_output/live/report.json
```

| Target | Arm | Valid / attempts | Accepted observations | Median all attempts | Actual API credits | Credits / accepted observation |
|---|---|---:|---:|---:|---:|---:|
| Static catalog | Requests | 10/10 | 30 records | 55.77 ms | No API charge | Total USD unmeasured |
| Static catalog | Playwright | 10/10 | 30 records | 237.26 ms | No API charge | Total USD unmeasured |
| Static catalog | ScrapingAnt raw | 10/10 | 30 records | 692.28 ms | 10 | 0.3333 |
| Static catalog | ScrapingAnt rendered | 10/10 | 30 records | 1331.14 ms | 100 | 3.3333 |
| Delayed diagnostic | Requests | 0/10 | 0 sentinels | 51.90 ms | No API charge | Total USD unmeasured |
| Delayed diagnostic | Playwright | 10/10 | 10 sentinels | 2028.79 ms | No API charge | Total USD unmeasured |
| Delayed diagnostic | ScrapingAnt raw | 0/10 | 0 sentinels | 695.07 ms | 10 | Undefined: no accepted result |
| Delayed diagnostic | ScrapingAnt rendered | 10/10 | 10 sentinels | 3106.86 ms | 100 | 10 |

Every API response had outer and target HTTP status 200 and an expected credit receipt. This includes the ten charged raw diagnostic outputs that failed validation. No acquisition timed out and no retry was made. The rendered diagnostic observed range was 3013.67–6754.54 ms; the slowest attempt remains in the captures. Initial browser launch was 228.74 ms, excluded from per-attempt timing and reported separately.

Same installed versions as the local run. No concurrent blog build or rendering audit ran during the public-origin acquisition; other host activity was not controlled. Client region and provider browser implementation remain unknown. Direct arms reach GitHub Pages directly; API arms include client-to-service transit and managed acquisition through datacenter proxies. These paths measure each acquisition stack in this sample, not intrinsic Python-library speed.

`verify_capture.py` is the recommended offline verification command. It requires complete fixture and live-runtime hash maps, expected receipts for completed API rows and a receipted total within the approved cap. It then checks the canonical schedule, all attempt counts, body/source hashes, output decisions and summary using the byte-identical recorded replayer. Incomplete unknown-billing evidence remains explicitly incomplete. The original `runner.py --replay` option performs mechanical recomputation and does not replace these additional provenance/receipt checks. Hashes protect file integrity; they do not authenticate provider billing or independently audit the account ledger. Legacy local captures without runtime hashes are labeled `runtime_hashes_present=false`.

## Interpreting cost and uncertainty

Actual credits per accepted observation = sum of **every** attempt's `Ant-credits-cost` receipt / accepted observations. Charged invalid output belongs in the numerator. An absent receipt makes actual cost unknown; zero accepted observations makes the ratio undefined. Local methods consume no ScrapingAnt credits, but their total cash cost was not measured and is not zero by assumption.

The report provides median all-attempt latency, median valid-attempt latency, observed range and a Wilson 95% interval for repeated fixture attempts. Ten successes have interval approximately 72.2–100%; zero successes approximately 0–27.8%. Repeats share targets/environment and are not independent production-site samples. These intervals do not estimate production uptime, and ten samples do not establish p95/p99. Paired differences can describe the rounds, not prove a population winner. Keep any live public-origin timing separate from local loopback timing.

Total-cost model: `(allocated subscription + compute + additional proxies + setup/maintenance labor) / accepted observations`. Use supplied rates, utilization and amortization periods. Bundled managed proxy/browser charges must not be counted a second time. No host-cost, labor-saving or break-even number is measured here.

Primary documentation checked October 9: [Requests sessions/timeouts](https://requests.readthedocs.io/en/latest/user/advanced/), [Playwright page navigation/selectors](https://playwright.dev/python/docs/api/class-page), [API parameters](https://docs.scrapingant.com/request-response-format), [selector readiness](https://docs.scrapingant.com/wait-for-selector), [credits](https://docs.scrapingant.com/credits-cost). The public source and runtime are not inferred to be identical beyond measured fixtures.
