# Bounded employer job-posting collection

Evidence packet for https://scrapingant.com/blog/scraping-for-labor-market-intelligence-jobs-skills-and-wage

This packet demonstrates acquisition, validation and refresh for one **owned, fictional employer HTML contract**. It also replays retained fields from one genuine public Greenhouse Job Board GET. The default runner uses loopback HTTP and stored JSON only. It never makes a ScrapingAnt, OpenAI or live ATS request, even if an API key is present.

## Run

Use CPython **3.12.11**, the exact recorded runtime in `.python-version`. No third-party packages are required. Set `PYTHON_BIN` if that executable has a different name.

```bash
PYTHON_BIN=python3.12 ./run.sh
```

The command runs the tests, captures the local demonstrations in `expected_output/`, and verifies them against independent literal oracles. Ports and actual UTC observation timestamps vary between runs. It exits nonzero if any test, oracle or invariant fails. To check without changing stored captures:

```bash
PYTHON_BIN=python3.12 ./run.sh --check
```

For a manual CLI run, keep the fixture server running in one terminal:

```bash
python3.12 fixture_server.py --port 8873
```

In another terminal:

```bash
python3.12 collector.py --start-url 'http://127.0.0.1:8873/careers/roles?page=1' --max-pages 3
```

The collector prints JSON and returns **0** for a complete validated acquisition, **2** for a partial acquisition. The runner tests both exit statuses. `--previous baseline.json` adds refresh results. Save stdout only after checking the exit status, `complete`, counters and failures; a partial snapshot may contain retained older records with their original `observedUTC` values.

## Files and contract

- `collector.py`: bounded direct HTTP, no redirect following, fixed page/record URL policy, HTML adapter and refresh.
- `schema.py`: required nonblank job ID/title/employer/location/source URL/application URL/UTC observation; optional source date remains null when missing.
- `scrapingant_transport.py`: explicit opt-in `/v2/general` HTML retrieval; request shape and response acceptance are tested with local mocks. No extraction endpoint is used.
- `fixture_server.py`: local fixture scenarios, including HTTP 503, HTML error page with HTTP 200, duplicate/conflicting IDs and unsafe pagination.
- `fixtures/expected-records.json`: independently authored literal full-record oracle for the HTML fixture. Only the loopback origin and controlled timestamp are substituted.
- `greenhouse_replay.py`: a separate stored-list projection adapter; no live fetch and no pagination claim.
- `fixtures/greenhouse-expected-ids.json`: independently listed expected post IDs, with one full-record oracle in the tests.
- `test_collector.py`: record, provenance, pagination, refresh, CLI, feed and offline managed-request controls.
- `demo.py`, `verify_captures.py`: produce outputs and compare saved/fresh records, summaries and failure matrix.
- `evidence.yaml`: source provenance, versions, denominators, limitations and claims.

`SourcePolicy` and `ListingParser` deliberately recognize only this fictional Northstar contract: `/careers/roles?page=1`, an explicit list envelope and declared page sequence, `NS-000` IDs, and same-origin job/application links. Before using another authorized employer source, inspect its actual HTML or structured data and replace the adapter and URL policy, write source-specific literal records, and revalidate completeness. Changing the transport does not adapt selectors or establish permission.

Duplicate identical cards produce one record. Conflicting versions of an ID are excluded from the acquired records and make the run partial. Missing required fields, inconsistent page metadata, unrecognized/error HTML, unsafe next links, a loop, an exhausted page budget or an HTTP failure also make it partial. An empty list is accepted only through this source's explicit recognized empty state. For a partial refresh, prior unseen records are retained and `removed_ids` stays empty. A complete run's `removed_ids` means **absent from this source's validated listing**, not proof a role was filled or employment changed. There is no cross-employer identity resolution or labor-market inference.

## Genuine Greenhouse observation, separately scoped

The recorded public GET was https://boards-api.greenhouse.io/v1/boards/greenhouse/jobs on **2026-10-11T21:03:15.995679+00:00**. It returned HTTP 200 with `meta.total=19` and 19 job posts. The [official Job Board API documentation](https://docs.greenhouse.io/job-board.html) describes published-job GET endpoints as publicly available without authentication. This is an observed single-board JSON availability result, not broader ATS permission, HTML coverage or a ScrapingAnt test.

The saved file is a **projection** retaining only `id`, `title`, `location`, `absolute_url`, `updated_at` plus capture metadata. `capture.response_sha256` records the hash of the full response at acquisition, before projection. That full response is not distributed here, and its hash **cannot be reproduced from the projected file**. `evidence.yaml` separately records the saved projection file's hash. These hashes identify different artifacts.

The replay preserves `updated_at` as `source_updated_at`; it does not relabel it a posting date. The employer label is a caller-supplied value. A distinct application URL was not verified from this retained listing, so `applicationURL` stays null and `validated_for_refresh=false`. All 19 results are candidates; they do not enter the validated HTML refresh sink. Prefer an authorized official feed/API when it supplies your required fields; inspect any existing structured data before adding an HTML parser. Direct HTTP is sufficient if it returns the complete permitted HTML.

## Optional managed HTML retrieval

The `/v2/general` endpoint returns HTML. Our request uses `browser=false` or `browser=true` explicitly, `proxy_type=datacenter`, `proxy_country=us`, `timeout=30`, `return_page_source=false`. The code reads `SCRAPINGANT_API_KEY` from the environment and sends it in a header; it is never put in a request URL or printed. The header contract was checked in the current router source and exercised by the separate owned raw call below; the public OpenAPI describes query authentication only. Validate API HTTP status, target status, target media type/body size and your source schema separately. The [original target content-type](https://docs.scrapingant.com/custom-headers) uses `Ant-original-header-content-type`; explicit non-HTML target types are rejected. Missing target content-type is unknown and deferred to the required listing schema. The outer response need not carry a content-type and does not prove the target media type. Managed `NoRedirect` controls API-endpoint redirects, not redirects followed during remote target acquisition. See [request/response documentation](https://docs.scrapingant.com/request-response-format).

One separate call through the unchanged `managed_html` transport fetched the existing [owned raw fixture](https://scrapingant.github.io/scrapingant-examples/fixtures/dynamic-delayed.html) from **2026-10-11T21:38:39.695211 to 21:38:40.432850 UTC**. It returned API HTTP 200, target HTTP 200, an `Ant-credits-cost` receipt of **1**, and **752 bytes**. The captured body matches the pinned fixture source and contains the initial marker `<div id="test">Web Scraping is hard</div>`. [Receipt and source pins](expected_output/live-managed-2026-10-11/receipt.json) and the [captured HTML](expected_output/live-managed-2026-10-11/response.html) are retained; SHA-256 is `d670add5613e47f7e29d08480a1eec2b2fca04e94e18eba4628fe44e9b124e93`. Parameters were `browser=false`, `proxy_type=datacenter`, `proxy_country=us`, `timeout=30`, `return_page_source=false`.

This single observation establishes owned raw HTML transport and marker acceptance. It does not validate an employer/ATS HTML source, the job parser, pagination, managed CLI or JavaScript rendering. The default runner remains offline and does not repeat the call.

After permission and source-adapter validation, this opt-in job-source command illustrates the managed path. **This command was not executed for the packet and can consume credits.** `CAREERS_URL` must describe the adapter you have validated; the bundled fixed adapter rejects other URL shapes.

```bash
: "${SCRAPINGANT_API_KEY:?set it in your environment}"
: "${CAREERS_URL:?set one authorized careers URL}"
python3.12 collector.py --start-url "$CAREERS_URL" --max-pages 3 \
  --transport scrapingant --browser false --allow-live-api
```

Use `--browser true` only when your source needs rendered HTML and its result passes the same validation. The single raw fixture receipt does not measure cost per valid job, target success rates or rendered acquisition. This packet does not support arbitrary Indeed/LinkedIn sources, an inventory service, applications or profiles.

As checked in current documentation on October 11, ordinary non-Google datacenter retrieval is documented at **1 API credit** without a browser and **10 API credits** with JavaScript rendering. These are documented request costs, not measured valid-job yield. Check the current [credits schedule](https://docs.scrapingant.com/credits-cost) and [plans](https://scrapingant.com/#pricing). The current free plan lists 10,000 monthly API credits and no credit card; Enthusiast lists 100,000 credits for $19/month. No paid or free-provider request was made by the runner.

## Review/publication state

AI-assisted evidence implementation and draft. Named-author methodology review and independent review of this capture update are pending. The article remains unlisted; this packet establishes reproducibility within its stated boundaries and does not authorize restoration or deployment.
