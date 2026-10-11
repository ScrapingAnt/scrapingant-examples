# One extraction contract, three representations

Status: completed offline preservation study and 15 authenticated hosted MCP calls. Fresh bounded approval was granted October 11:15 retrieval attempts/15 credits and60 model attempts/US$0.25. Two model requests failed before inference: an explicitly authorized continuation skipped the first failed job before attempt 2 also failed. Both lack usage/completion. The runner stopped without retry; no model accuracy or cost per correct model output exists.

## Reader task and contract

Return every product in the designated product region, in document order, with exactly `name`, `displayed_price`, `units_sold`, `share`, `sku`, and `buy_url`. Preserve displayed strings, resolve relative links against the supplied source URL, and use null only when that region lacks a field. Do not infer SKU from a URL. No extra products or fields, duplicate rows, coerced numbers, or guessed destinations.

The fixed task identifies the four-column `Product`, `Price`, `Units sold`, `Share` table in the imported catalog, or the product offers under `Desk lamps` / `Travel bottles` in the other cases. Other demonstration tables and documentation links are outside the product region. Every representation still contains the full source conversion; this is task selection, not arm-specific cropping.

The literal oracle is `ground_truth.json`; it is specified separately from the representation generator and never derived from parser output. The fixture author and oracle writer are the same AI execution session, so this is procedural independence, not an independent human labeling exercise. A fresh reviewer must inspect both.

## Frozen inputs

1. `catalog.html`: the first static Requests capture in the previous acquisition study's final live report (`body-007.html`), from examples source `9e5fba96d34a7bb7106a5a0e478a668078c6a312`. Reuse original bytes and record their SHA-256; no new fetch. Three records.
2. `links.html`: an authored, local-only two-product catalog with visible SKUs and identical `Buy` link labels but distinct destinations. Nav, cookie and footer text make whole-page conversion visible.
3. `attributes.html`: an authored, local-only two-product catalog whose SKUs exist only in `data-sku`; names/prices and links remain visible.

The task/schema stays fixed for all three cases. Two deliberately adversarial cases isolate information loss; this small selected set is not representative of the web. Local fixtures stay inside this example, outside the GitHub Pages top-level `fixtures/`. No new public endpoint.

## Comparable format generation (offline)

HTML is the exact saved source, decoded as UTF-8. Markdown runs the inspected converter recipe at extractor source `66d10caea9a90df3c14069bfd910b92f1ad1123a`: BeautifulSoup 4.12.2 `html.parser`, remove script/noscript, html2text 2020.1.16 defaults with `ignore_links=False`. No reader-mode, cropping, summarization, link repair or arm-specific cleanup.

Text uses local Chromium selection (`Range.selectNode(document.documentElement)` then `window.getSelection().toString()`), matching the inspected browser worker's selection recipe at `11cc9f570656298f736979f548c5659c57b64b57`. All network requests are aborted, document scripts are disabled, and every arm starts with the same saved HTML. This is a local reference transformation; it is not the deployed MCP text result or a verification of raw-mode text behavior.

Five local repeats per case/arm check byte determinism, not independent site observations. Count exact representation UTF-8 bytes and content-only tokens with tiktoken 0.11.0 `o200k_base` and `cl100k_base`, including tokenizer asset hashes. Token counts exclude prompts, schema, tool envelopes and billing overhead. They are not observed model charges.

## What is measured now

For each non-null oracle field, test whether its required literal survives in the representation (link URLs may be present relative to the supplied base). The current relative-URL fallback checks pathname only. Every purchase URL in these selected cases has no query or fragment. Before adding query/fragment-sensitive destinations, extend and test that checker; the current score does not establish their preservation. Report all slot results and denominators. Repeated identical values count as separate expected slots; lexical survival does not verify row association, exact-record output or model comprehension.

Counterfactual probes change only link destinations or only `data-sku` values. If two different HTML sources produce identical text/Markdown, a consumer of that representation alone cannot distinguish the changed fields. This proves loss for the selected transform and fixture; it says nothing about model accuracy for retained fields.

## Fixed model experiment — two pre-inference failures, remaining work blocked

Freeze model `gpt-4.1-mini-2025-04-14`, Chat Completions, temperature=0, top_p=1, max_completion_tokens=1000, no tools/retrieval/history, no retries, identical system/task/schema and source URL. Use five randomized/interleaved repeats for each of 3 cases × 3 arms = 45 calls. Also evaluate each of the proposed 15 live MCP returns with the same task = at most 60 calls total. Maximum input per request, including prompt/schema overhead: 5000 tokens. Stop before any call exceeding either cap. Repeats describe this model/run only; temperature=0 does not imply determinism.

Record request/task/model/settings hashes, UTC start/end, full response and refusal/truncation/errors, reported model version/system fingerprint if supplied, token usage including cached input, and actual token-rate cost. Exact ordered record equality is the primary accepted-page denominator; correct field slots are secondary. Charge every failed/truncated/incorrect attempt to the numerator. Zero accepted pages => cost per accepted page is undefined. Do not pool unlike tasks or declare a universal winner. Do not drop trials, failures or slow observations.

## Hosted MCP experiment —15 calls executed

Executed using only the existing owned static fixture: `https://scrapingant.github.io/scrapingant-examples/fixtures/html-tables.html`. Initialize one explicitly versioned MCP client, save tools/list schemas, then 3 tools × 5 randomized/interleaved rounds = 15 tools/call requests. Force browser=false, proxy_type=datacenter, proxy_country=US for every arm, no retries, no residential/browser fallback. This is a static acquisition check, not interactive agent planning or browser rendering reliability. Local-only richer cases will not be published to enable live fetching.

Save JSON-RPC requests, response bodies/headers, tool outputs, error strings/isError, elapsed time, source URL, UTC time, and response hashes. The live calls reacquire the fixture, so they cannot establish identical source captures: check against the frozen source and report drift/unknown provenance. Report live acquisition separately from offline same-capture representation results. A successful transport can carry an error string or incomplete content; validate against the oracle.

MCP documentation says these calls use normal retrieval credits. At browser=false/datacenter the documented estimate is 1 credit per successful request: a new ceiling of 15 credits. The inspected tool returns content without per-call credit receipts. A separately authorized existing read-only SQL route verified the expected non-elevated SELECT-only role, primary database, exact test-account scope and one active period. The initial snapshot and 15 post-call snapshots increased by 1 each:15 contemporaneous account credits. No usage API was invoked because source inspection found conditional subscription repair. Account snapshots are not exclusive per-request receipts: concurrent traffic cannot be ruled out. Cost per model-correct output remains unmeasured.

## Bounded execution and current stop

MCP 15/15 attempts completed. Model attempt 1 failed before inference. A separately owner-authorized continuation preserved the exact stopped private checkpoint, its first row/response and US$0.0036 reservation; it skipped the first planned job and started attempt 2 with the same saved inputs/model/settings. Attempt 2 also failed before inference without usage/completion. It stopped immediately, without retry, purchase, model/account fallback or another MCP call. Operational configuration and provider-message details are excluded from public artifacts.

Both unknown-charge attempts remain reserved: US$0.0072 is conservative allowance accounting, not an observed charge. Cumulative count is 2/60, leaving at most 58 attempts and US$0.2428 unreserved under the overall US$0.25 cap. No billing receipt or zero charge is inferred. The next unexecuted planned job is attempt 3; do not retry either failed job or silently create a fresh 60-call run. The current second stop requires a separately reviewed, expressly authorized continuation that carries this prefix and accounting. No valid inference response exists, so accuracy, uncertainty intervals and cost per correct output remain undefined.

Public hosted captures are in `expected_output/live-mcp-2026-10-11/`; the provider failure is in `expected_output/live-model-2026-10-11/`. Operational provider error messages and account-counter absolute balances/internal period reference were omitted from public copies; HTTP statuses, pre-inference failure markers and minimization hashes remain. Raw private originals were retained outside repositories; public hashes identify the exact downloadable artifacts and private-original hashes document that minimization. HTTP body captures use Requests' decoded response text; credential-bearing response headers are excluded. No receipt or model outcome is fabricated.

HTML and Markdown matched their local catalog references in all 5 observations. Hosted browser=false text was 1083 bytes/436 o200k/440 cl100k tokens, retained the document title and CSS-hidden stock row, and flattened cells to newline-separated strings. Local browser-selection text was 1051 bytes/415 o200k/416 cl100k tokens. Both contained the 12 required table literals; neither lexical check establishes model extraction accuracy. Five hosted HTML outputs matched the frozen source hash; separate Markdown/text calls do not expose underlying source bytes. No hosted browser-mode or richer local-case acquisition was executed.

`mcp_live.py` and `model_run.py` are explicit opt-in runners, independently reviewed before dispatch; default `run.sh` stays offline. MCP ordering uses seed 8, five rounds with all 3 arms interleaved. Model plan uses seed 8,45 same-capture jobs followed by15 hosted-output jobs, common frozen task/schema/system/settings, full serialized request tokenization plus 256 framing tokens before dispatch. All 60 planned inputs preflighted at 751–2375 tokens, below 5000. A request reserves 5000 input + 1000 output cost before transport; every unknown outcome stays reserved and stops, no hidden retries, redirects, model/tier/account fallback or automatic existing-output overwrite. The explicitly approved rebind preserved the exact stopped checkpoint before appending attempt 2; ordinary fresh-run mode refuses an existing directory. API-reported model/tier/usage and exact records are checked before another attempt. Guard tests use synthetic transport boundaries only; they are not service-performance evidence.

Approved bounded model ceiling: US$0.25, at most 60 calls. Official model page checked 2026-10-11 lists standard text input $0.40/M and output $1.60/M. Worst permitted token allocation: 60 × (5000 × 0.40/M + 1000 × 1.60/M) = $0.216, below $0.25. No cached-input discount assumed. Stop on unknown/missing usage; reserve the full maximum before each request. No purchasing credit, adding payment methods or using other models is authorized. The explicitly authorized continuation stopped before any inference response. No model completions or reported model token usage exist. The analysis code separately counts inference responses (including refusals/truncation) and attempts, keeps unknown-charge totals null, and forms matched-repeat comparisons only when all three arms have inference. Nominal Wilson intervals, if later populated, describe same-input repeats under an independence approximation; correlated repeats and seven selected products cannot support website-population inference. No interval is reported for this zero-inference run.

Sources: https://developers.openai.com/api/docs/models/gpt-4.1-mini ; https://docs.scrapingant.com/mcp-server ; https://docs.scrapingant.com/credits-cost ; https://docs.scrapingant.com/llm-markdown (checked 2026-10-11).

## Interpretation and publication gates

Preservation, tokenization, LLM extraction and live MCP behavior are separate outputs. No token reduction/local replay proves production reliability, engineering savings, rankings or paid conversion. Paying-customer success means first-time paid customers; clicks/signups are intermediate events. There is no analytics implementation or customer-attribution result in this packet.

Draft source PRs may present completed offline and hosted acquisition evidence plus explicitly blocked model measurements. Publication requires the named author Oleg Kulyk's methodology/conclusions/byline review and an explicit decision about the missing live/model evidence. Keep article `draft: true`; no source merge, deployment, Terraform or issue closure is authorized.
