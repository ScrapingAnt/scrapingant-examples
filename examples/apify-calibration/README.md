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

An optional `--build` validates only the syntax of a public immutable build number. It performs no lookup and does not establish that a build exists, is maintained, or matches reviewed source. Tags such as `latest` are rejected. No actual public build has been selected. The build used by the tests is explicitly fictional.

The tests use synthetic transport responses and in-memory HTTP doubles. They check token access ordering, one start with no retries, polling limits, exact options, owned URL and payload allowlists, build confirmation, output validation, bounded reads, redirect rejection, and sanitized HTTP errors. No test contacts Apify, reads a real token, or deletes resources.

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
| Client operations | At most one start, three run polls with `waitForFinish=60`, and one JSON export with `limit=2` and five fixed fields |
| HTTP | HTTPS on the fixed API host, header authentication, no redirects or retries; each response read is limited to 128 KiB plus one overflow byte |

The page function makes no explicit network, enqueue, snapshot or storage calls. The Actor and SDK still create queues, key-value records, sessions, metadata and other operational data. Disabling optional browser behavior does not prove that those volumes or browser/network overhead are bounded. The Actor's page limit documentation also cautions that the actual loaded page count can exceed the requested limit; the two fixed start URLs and empty link selector constrain intended scope, but do not replace a reviewed build-level bound.

Only accepted fixture fields may appear in a successful output. Raw HTTP responses, run/storage/account identifiers, authentication headers, token values, provider logs, and error bodies are never printed or uploaded by the runner. An ambiguous start failure stops after that request; a new dispatch must not be treated as a safe retry. The runner has no purchase, upgrade, account-setting, build-creation, abort, restart, resurrection, or deletion route.

## Why the total cost guard stays closed

The policy budget is **USD 1 total incremental cost, using existing credits only**, for two pages and one run. The proposed run cap is USD 0.10. Current [Run Actor API documentation](https://docs.apify.com/api/v2/actors-runs-post) describes `maxTotalChargeUsd` as a total run-cost cap across all pricing models. That establishes the documented scope of the run parameter; it does not establish an account-wide ceiling or cover all future storage and export charges.

At the current Free rate of USD 0.20/CU, the nominal calculation `1 GB × 120 / 3600 hours × 0.20` is about USD 0.006667. This is a compute-only illustration, **not an upper bound**: build-specific behavior and platform startup/termination accounting remain unresolved. [Apify pricing](https://apify.com/pricing) is the dated rate source.

The following evidence is still required before opening the guard:

1. Select an existing immutable public build, connect it to reviewed Actor source and resolved SDK dependencies, and establish actual storage/operation behavior. A mutable source branch is not proof of the deployed build.
2. Bound retained dataset, KV and request queue bytes, including input, session state, statistics, debug/error metadata and SDK persistence. Two small output records do not bound all retained storage.
3. Establish retention duration or an approved cleanup deadline. [Storage documentation](https://docs.apify.com/storage) describes four-month retention for the latest ten Free runs; [runs and builds documentation](https://docs.apify.com/actors/running/runs-and-builds) describes latest-ten retention indefinitely. The [dataset page](https://docs.apify.com/storage/dataset) gives a generic seven-day unnamed-storage rule. Seven days cannot be assumed for this run.
4. Bound post-run reads, export/transfer, storage operations and termination overhead, including costs incurred after polling stops. [Store Actor documentation](https://docs.apify.com/actors/running/actors-in-store) says post-run interactions are charged separately for all pricing models. A local response-size limit bounds the client's read, not necessarily provider-side billing.
5. Obtain a reviewed all-meter USD bound within the budget through either audited finite retention or reliable cleanup. A policy that calls for deletion also requires separate owner approval for the exact resources, timing and deletion action; a proven finite-retention bound does not require deletion permission. Confirm the one-run authorization remains unused before any later execution. A workflow run-attempt check prevents workflow reruns; it does not prevent a second distinct manual dispatch.

For known quantities only, the timed storage function calculates `hours × ((dataset_GB + KV_GB) × 0.001 + queue_GB × 0.004)` using decimal arithmetic and the Free/Starter USD/GB-hour rates on the [storage page](https://docs.apify.com/storage). Unknown bytes or duration are rejected; they never default to zero. This formula excludes operations and transfer, which need their own bounds.

Cleanup is deliberately absent. Deleting a run cannot be assumed to delete its storage or eliminate all retention charges; the [run deletion API documentation](https://docs.apify.com/api/v2/actor-run-delete) does not establish that guarantee. No resource is scheduled for deletion by this package.

## Workflows and token handling

[The manual workflow](../../.github/workflows/apify-calibration-manual.yml) has only `workflow_dispatch`, read-only repository permissions, a main-only job, a pinned dispatch commit checkout with persisted credentials disabled, and an execution boolean that defaults to false. It rejects workflow reruns. The offline checks and readiness step have no token. The token is referenced only in the later live step, which cannot run while the preceding closed-guard check fails. Nothing uploads provider/account logs or artifacts automatically. Repository branch protection is managed outside this package; this workflow does not configure it.

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
| [Pricing](https://apify.com/pricing), [storage](https://docs.apify.com/storage), [runs and builds](https://docs.apify.com/actors/running/runs-and-builds), [dataset](https://docs.apify.com/storage/dataset), [Store Actors](https://docs.apify.com/actors/running/actors-in-store), [run deletion](https://docs.apify.com/api/v2/actor-run-delete) | Dated rates and unresolved all-meter retention/export/cleanup guard |
