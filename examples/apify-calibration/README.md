# Apify calibration — single dispatch consumed, guard closed

**Workflow37018036109 was dispatched once at commit7e6e4deb314e997c40f06194dc1e78ca88c92f1e on October2.** The source guard is now closed again to block any further execution. That workflow checks out its exact dispatch commit, so this closure does not interrupt its approved capture/cleanup. Outcome is pending verification; this note makes no consumption or cleanup claim. [Single workflow](https://github.com/ScrapingAnt/scrapingant-examples/actions/runs/37018036109).

Do not rerun or start another dispatch. Default CLI operation and all tests remain offline and use no real token.

Future start/poll failures retain a sanitized `failure_diagnostic`: the operation, numeric HTTP status (or null if none was observed), fixed error category and validation stage, and a known run-status enum when available. This distinguishes an HTTP rejection from an HTTP 201 response whose JSON, build, options or resource references failed validation. A successful HTTP status alone does not establish a validated run or its cost. Raw messages, bodies, URLs, headers and identifiers remain excluded. This offline diagnostic change adds no retries or provider actions and keeps the guard closed. The earlier receipt's `UNKNOWN` status and null run receipts cannot recover the cause of the October 2 dispatch; these new fields must not be inferred retroactively.

## Historical activation record

# Apify calibration — one authorized dispatch

**October2 activation:** source build3.0.25 is pinned to official commit21de8bf52ca7a587e680635a4198abfada472a8e with frozen Crawlee3.18.1, Apify SDK3.7.2 and Puppeteer25.4.0 dependencies. Independent cleanup review passed39 mocked tests on Python3.10/3.12 and12 additional probes. Explicit approval covers one run on these two owned pages using existing credits, USD1 total, and permanent deletion of only its three newly created default stores after verified sanitized evidence capture. The implementation's15-minute cleanup window is tighter than the approved1h. No provider run has occurred at this activation commit.

The reviewed guard temporarily permits this **one manual dispatch**. Do not start another distinct workflow or rerun it. The guard will close after this attempt. Default CLI operation remains an offline plan; no token is read by plan/tests.

The ordinary-operation planning reserve is USD0.101542926832, rounded up to USD0.11: USD0.10 documented all-model run cap, USD0.000452984832 storage reserve, USD0.0007 client operations and USD0.000389942 transfer. Storage assumptions are dataset324MiB, KV36MiB and queue18MiB for1h; operations assume14 calls at the highest listed per-operation rate; transfer assumes14×(131073 response +8192 request/header bytes) at0.20/decimalGB. These are generous **supplied planning reserves**, not observed/source-enforced byte limits or a guarantee against arbitrary provider/network failure. The fixed source writes only a handful of ordinary JSON keys/records, but error/cookie metadata has no formal byte cap. Failed/ambiguous execution or cleanup is explicitly unresolved; stop without retry.

The run cap and rates come from [Run Actor API](https://docs.apify.com/api/v2/actors-runs-post), [current official pricing](https://apify.com/pricing) and [Web Scraper usage pricing](https://apify.com/apify/web-scraper/pricing), checked2026-10-02. [Pinned Dockerfile](https://github.com/apify/actor-scraper/blob/21de8bf52ca7a587e680635a4198abfada472a8e/packages/actor-scraper/web-scraper/Dockerfile) and [lockfile](https://github.com/apify/actor-scraper/blob/21de8bf52ca7a587e680635a4198abfada472a8e/pnpm-lock.yaml) establish build-source provenance. This is a charge/input calibration, not a production runtime benchmark or an invoice.

## Historical preparation record — guard closed before this activation

# Apify calibration preparation — execution blocked

This separate example prepares a manual calibration of two owned synthetic HTML fixtures with `apify/web-scraper`. It has **not executed an Actor**. Its plan and mock responses are not consumption measurements, invoices, savings evidence, or evidence of a cheapest plan. The existing modeled `apify-pricing` example is separate.

The source-controlled `REVIEWED_GUARD` in [calibration.py](calibration.py) is closed. `--execute` and `--check-readiness` exit with code 2 before reading `APIFY_TOKEN` or constructing a real HTTP transport. No flag or environment variable opens this gate. A later reviewed code and guard update is required.

## Run offline

Python 3.10 or 3.12 and its standard library are sufficient; there are no dependencies to install.

```sh
cd examples/apify-calibration
./run.sh
python3 calibration.py                    # default: offline plan
python3 calibration.py --plan             # explicit offline plan
```

An optional `--build` validates only the syntax of a public immutable build number. The runner performs no build lookup. Separate public metadata review identified existing successful build **3.0.25**, source commit **21de8bf52ca7a587e680635a4198abfada472a8e**, as the candidate. The public Actor identity is pinned in code. This does not establish an all-meter cost bound or open the live guard. Tags such as `latest` are rejected; tests use a fictional build and explicitly patched closed/open mock policies.

The tests use synthetic transport responses and in-memory HTTP doubles. They check token access ordering, one start with no retries, polling/deadline limits, fixed scope, build/ownership confirmation, output validation, durable evidence ordering, HTTP 204/404 handling, independent cleanup failures, bounded reads, and sanitized HTTP errors. Atomic file persistence is tested only with synthetic JSON in temporary directories. No test contacts Apify, reads a real token, or deletes provider resources.

## Fixed proposed scope

| Constraint | Unexecuted request |
|---|---|
| Actor | `apify/web-scraper`, maintained by Apify; immutable public build required |
| Pages | [complete.html](https://scrapingant.github.io/scrapingant-examples/fixtures/mcp-catalog/complete.html), 290 bytes; [changed-layout.html](https://scrapingant.github.io/scrapingant-examples/fixtures/mcp-catalog/changed-layout.html), 422 bytes at source check |
| Actor mode | `PRODUCTION`; maximum concurrency 1 |
| Page/result limits | 2 pages, 2 results; no followed links or page retries |
| Run options | 1024 MB, 120 seconds, `maxTotalChargeUsd=0.10`, `restartOnError=false` |
| Browser options | No proxy, media/CSS download, jQuery injection, scrolling, cookie modal extension, or custom navigation hooks |
| Extraction | Read the first paragraph, require at most 128 characters and the exact expected AA101 product text; return five fixed fields |
| Acceptance | Exactly one `AA101` Desk Lamp record per fixture, 3499 USD minor units; `(fixture, sku)` is the unique key |
| Client operations | At most 14 calls: one start, three run polls, one filtered export, three metadata reads, three store deletes, three absence reads |
| HTTP | HTTPS on the fixed API host, header authentication, no redirects or retries; each response read is limited to 128 KiB plus one overflow byte |
| Time budget | Start 30s, polls 65s, export/metadata/delete/absence 10s each; 325s maximum requested waits, 480s local wall cap, at least 360s remaining before token/start, 100s reserved for cleanup |

The page function makes no explicit network, enqueue, snapshot or storage calls. The Actor and SDK still create queues, key-value records, sessions, metadata and other operational data. Disabling optional browser behavior does not prove that those volumes or browser/network overhead are bounded. The Actor's page limit documentation also cautions that the actual loaded page count can exceed the requested limit; the two fixed start URLs and empty link selector constrain intended scope, but do not replace a reviewed build-level bound.

Outputs contain accepted fixture fields and allowlisted numeric run/storage receipts. Raw HTTP responses, run/storage/account identifiers, authentication headers, signed URLs, signing keys, token values, provider logs and error bodies are never printed, persisted or uploaded. The initial three default IDs and owner identity remain only in memory. An ambiguous start failure stops after that request; a new dispatch must not be treated as a safe retry. The runner has no purchase, upgrade, account-setting, build-creation, abort, restart, resurrection, account enumeration or run-delete route.

## Why the total cost guard stays closed

The policy budget is **USD 1 total incremental cost, using existing credits only**, for two pages and one run. The proposed run cap is USD 0.10. Current [Run Actor API documentation](https://docs.apify.com/api/v2/actors-runs-post) describes `maxTotalChargeUsd` as a total run-cost cap across all pricing models. That establishes the documented scope of the run parameter; it does not establish an account-wide ceiling or cover all future storage and export charges.

At the current Free rate of USD 0.20/CU, the nominal calculation `1 GB × 120 / 3600 hours × 0.20` is about USD 0.006667. This is a compute-only illustration, **not an upper bound**: build-specific behavior and platform startup/termination accounting remain unresolved. [Apify pricing](https://apify.com/pricing) is the dated rate source.

The following evidence is still required before opening the guard:

1. Finish the source/runtime and numerical review of candidate build 3.0.25 and its resolved dependencies. Public build existence and input-schema validity do not establish actual storage/operation bounds.
2. Bound retained dataset, KV and request queue bytes, including input, session state, statistics, debug/error metadata and SDK persistence. Two small output records do not bound all retained storage.
3. Establish retention duration or an approved cleanup deadline. [Storage documentation](https://docs.apify.com/storage) describes four-month retention for the latest ten Free runs; [runs and builds documentation](https://docs.apify.com/actors/running/runs-and-builds) describes latest-ten retention indefinitely. The [dataset page](https://docs.apify.com/storage/dataset) gives a generic seven-day unnamed-storage rule. Seven days cannot be assumed for this run.
4. Bound post-run reads, export/transfer, storage operations and termination overhead, including costs incurred after polling stops. [Store Actor documentation](https://docs.apify.com/actors/running/actors-in-store) says post-run interactions are charged separately for all pricing models. A local response-size limit bounds the client's read, not necessarily provider-side billing.
5. Obtain a reviewed all-meter USD bound within the budget through either audited finite retention or reliable cleanup. A policy that calls for deletion also requires separate owner approval for the exact resources, timing and deletion action; a proven finite-retention bound does not require deletion permission. Confirm the one-run authorization remains unused before any later execution. A workflow run-attempt check prevents workflow reruns; it does not prevent a second distinct manual dispatch.

For known quantities only, the timed storage function calculates `hours × ((dataset_GB + KV_GB) × 0.001 + queue_GB × 0.004)` using decimal arithmetic and the Free/Starter USD/GB-hour rates on the [storage page](https://docs.apify.com/storage). Unknown bytes or duration are rejected; they never default to zero. This formula excludes operations and transfer, which need their own bounds.

## Prepared cleanup and durable evidence

Cleanup is implemented for mock testing and remains disabled by the closed live guard. The live path requires a code-defined approved cleanup policy with a lifetime no longer than 15 minutes; no CLI flag can authorize deletion. It preserves the initial POST response's three default IDs and requires a confirmed terminal run. Metadata must match each original ID, user, run and pinned public Actor, have an explicitly null name, and have creation time within five seconds of the run lifetime. Access settings are not ownership proof; documented inherited/public settings do not override these association checks. A missing/mismatched association blocks every delete. No named/shared store or other resource is eligible.

Before any DELETE, the runner captures the allowlisted run usage, costs, charged-event counts without arbitrary labels, statistics, start/finish timestamps, the three storage-byte/operation receipts, and either both accepted records or a sanitized extraction-failure state. Missing numeric meters remain null. An injectable persistence callback must verify the expected SHA-256. The real default atomically replaces the fixed **`calibration-receipt.json`**, fsyncs its file and directory, and verifies exact readback and hash. It then flushes a sanitized pre-cleanup receipt to stdout. Persistence, verification or stdout failure prevents every delete.

The `finally` path attempts cleanup even when bounded export/extraction validation fails or the run terminates unsuccessfully. All metadata and durable evidence precede deletion. Each of the three verified stores receives at most one DELETE, then one GET must return HTTP 404 to confirm absence. Documented empty HTTP 204 success needs no JSON parsing. One failed delete does not stop independent store attempts; there is no retry. A still-active run, ambiguous polling, exhausted wall budget, unverified scope, or residual storage requires **owner attention**. Network failures, process termination or unavailable storage cannot be promised successful cleanup, and total incremental cost remains unknown in those cases. Do not rerun.

The final sanitized file retains the pre-delete capture, its timestamp/digest, cleanup completion timestamp/elapsed time and all absence outcomes, including on failure. Failed cleanup or evidence persistence returns a nonzero CLI exit. The run receipt is not a full invoice: later export, metadata, deletion, absence reads, transfer and retention charges are not fully reconciled. Deleting a run is never used as a substitute for deleting verified stores.

## Workflows and token handling

[The manual workflow](../../.github/workflows/apify-calibration-manual.yml) has only `workflow_dispatch`, read-only repository permissions, a main-only job, a pinned dispatch commit checkout with persisted credentials disabled, and an execution boolean that defaults to false. It rejects workflow reruns. Its first step records a monotonic job deadline before checkout/setup; the runner uses the smaller job/local deadline and refuses token access/start if less than 360 seconds remains. The offline checks and readiness step have no token. The token is referenced only in the later live step, which cannot run while the preceding closed-guard check fails. An always-run upload step preserves only the fixed sanitized receipt file for seven days if it exists; it uploads no raw logs, resource manifests or account responses. Repository branch protection is managed outside this package; this workflow does not configure it.

[The offline workflow](../../.github/workflows/apify-calibration-offline.yml) runs standard-library tests on Python 3.10 and 3.12 for main pushes and pull requests affecting this package or these two workflows. It references no secrets.

For any later approved live execution, authentication would be supplied solely through `APIFY_TOKEN` in the live step's environment, after opt-in and readiness validation. The CLI accepts no token argument. Authorization uses a redacted preview in plans and an HTTPS header in the transport; token query parameters and redirects are rejected. Do not paste credentials into issues, arguments, plans or saved logs.

## Primary source record

Public source checks are dated **2026-10-02**. These are documentation/source reads, not provider execution or private account inspection. Rates and behavior must be rechecked before a future guard-opening change.

| Source | Used for |
|---|---|
| [Run Actor API](https://docs.apify.com/api/v2/actors-runs-post) | All-model run cap, memory/timeout, restart control, immutable build number and returned run options |
| [Web Scraper input](https://apify.com/apify/web-scraper/input-schema) | Maintained usage-only Actor; proposed input names and limits |
| [Actor source](https://github.com/apify/actor-scraper/tree/master/packages/actor-scraper/web-scraper) and [crawler setup](https://raw.githubusercontent.com/apify/actor-scraper/master/packages/actor-scraper/web-scraper/src/internals/crawler_setup.ts) | Operational storage/session behavior; mutable source only, not a verified deployed build |
| [SDK Actor proxy configuration](https://docs.apify.com/sdk/js/reference/class/Actor#static-createProxyConfiguration) | No-proxy configuration behavior; actual build dependencies remain unknown |
| [Dataset items API](https://docs.apify.com/api/v2/dataset-items-get) | Fixed field selection and export limit |
| [Dataset metadata](https://docs.apify.com/api/v2/dataset-get), [KV metadata](https://docs.apify.com/api/v2/key-value-store-get), [queue metadata](https://docs.apify.com/api/v2/request-queue-get) | Original ID/user/run/Actor association, nullable names and storage-byte/operation receipts |
| [Delete dataset](https://docs.apify.com/api/v2/dataset-delete), [delete KV](https://docs.apify.com/api/v2/key-value-store-delete), [delete queue](https://docs.apify.com/api/v2/request-queue-delete) | Only the three verified default stores; documented 204 responses and absence verification |
| [Pricing](https://apify.com/pricing), [storage](https://docs.apify.com/storage), [runs and builds](https://docs.apify.com/actors/running/runs-and-builds), [dataset](https://docs.apify.com/storage/dataset), [Store Actors](https://docs.apify.com/actors/running/actors-in-store), [run deletion](https://docs.apify.com/api/v2/actor-run-delete) | Dated rates and unresolved all-meter retention/export/cleanup guard |
