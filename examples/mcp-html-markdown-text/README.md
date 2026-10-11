# HTML, Markdown or plain text for one extraction contract

This packet backs the draft article “HTML vs Markdown vs Plain Text for LLM Extraction.” It separates same-capture field loss/tokenization, 15 hosted MCP acquisitions, and 58 fixed-model extraction responses. Two additional requests failed before inference and remain in the evidence with unknown charges. The completed run contains every planned attempt; no failed job was retried. See [PROTOCOL.md](PROTOCOL.md) for settings, provenance, budget accounting and limitations.

## Run the saved evidence

Python 3.12 and the pinned requirements are required. The browser selection reference was recorded with Chromium 151.0.7922.34 via Playwright 1.62.0; a different browser may produce different whitespace, in which case strict replay should fail instead of silently updating evidence.

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
./run.sh
```

Dependency/browser installation and the first tokenizer-cache population require internet access. They do not call ScrapingAnt retrieval or a model. Subsequent replay with the installed dependencies, browser and tokenizer cache is offline: the browser aborts every page network request, disables document scripts, and uses the saved fixtures. `run.sh` never runs public discovery or paid work, even if keys are configured. `TIKTOKEN_CACHE_DIR` may point to your own writable cache.

`run.sh` tests the strict output scorer, creates fresh reference transformations in a temporary directory, and compares source/oracle/task/runtime hashes, all nine outputs, every token/slot count and both counterfactuals against the committed report. It does not overwrite committed outputs. To deliberately create a separate local observation:

```bash
python replay.py --out run_output
```

## Files and interpretation

- `fixtures/`: original authorized acquisition-study catalog capture plus two local authored cases; not served as new GitHub Pages fixture URLs.
- `ground_truth.json`, `task.txt`, `contract.py`: literal records, common task and exact-page scorer. The model experiment must never send the oracle to the model.
- `replay.py`: exact HTML, inspected Markdown recipe, local browser selection reference, five repeats and content-only tokenization.
- `expected_output/report.json`, `summary.csv`, `summary.txt`: every field-slot result, all transformation hashes, versions and tokenizer vocabulary digests.
- `expected_output/*.counterfactual.*`: URL-only or SKU-only source changes and the indistinguishable derived representations.
- `discover.py`, `expected_output/public-discovery.json`: optional public, unauthenticated MCP schema discovery from October 11, 2026. Exactly initialize/initialized/tools/list; no tools/call, no environment credential lookup. This confirms the exposed tools and parameters, not their retrieval behavior.
- `sources/provenance.json`: imported-capture provenance and source inspection notes.

The nine rows report **literal presence among non-null expected slots**. Equal values in different records count as separate expected slots. Neither survival nor token counts prove correct associations or model extraction. The counterfactuals provide the stronger result: different required source facts become indistinguishable for a consumer limited to the lossy representation.

The fixed task selects the four-column catalog table or the offers under `Desk lamps` / `Travel bottles`; other demonstration tables and documentation links are outside that product region. Inputs and conversions remain complete. The current URL-presence fallback checks only pathname: all selected purchase URLs lack query/fragment components. Extend and test the checker before using those components in a new case.

The same fixed schema is used for all cases: name, displayed price, units sold, share, SKU, buy URL. Seven unique fixture records are reused; five local transformations are not five new sites or records. No universal accuracy, credit or cash-cost winner is claimed. Fixed-model outcomes are reported separately below.

## Optional public schema discovery

```bash
python discover.py
```

This makes three read-only unauthenticated requests to the existing hosted MCP endpoint and replaces the saved discovery observation. Do not run it as part of strict offline replay. It reads no credentials and cannot call a retrieval tool. Do not confuse transport discovery with an extraction run.

## Paid phase and publication

The approved run allowed at most 15 MCP attempts/15 credits and 60 fixed-model attempts / US$0.25. All 15 MCP attempts completed; account counters increased 15 in total, without per-call receipt/exclusive attribution. Model attempts 1 and 2 failed before inference. Their US$0.0072 reservation remains conservative allowance accounting, **not observed billing**. Separately authorized continuations preserved both checkpoints and failed rows, skipped both consumed jobs, and completed attempts 3–60 using the saved MCP outputs. No new credentials/accounts/purchases were created and no MCP call was repeated. The call cap is exhausted.

`mcp_live.py` and `model_run.py` are explicit opt-in runners, not called by `run.sh`. Do not rerun them against a paid account without bounded approval. Normal runs require a fresh directory. The exceptional `--continue-after-approved-auth-rebind` mode preserves a validated failed prefix; `--retained-attempts-at-approved-rebind 2` additionally carries the preceding checkpoint/history and both reservations. This recorded run had separate owner authorization and independent pre-dispatch review for each rebind. These flags do not grant approval. Another continuation, automatic retry, fallback or fresh-budget reset is rejected.

`expected_output/live-mcp-2026-10-11/` retains all 15 requests/responses/outputs and authenticated discovery. `expected_output/live-model-2026-10-11/` retains all 60 requests/responses and exact 58 completion strings. Operational error messages and account absolute counters/internal period identity are omitted from public copies; HTTP statuses, failure classifications and private-original/minimization hashes remain. Exact stopped checkpoints and responses are kept privately. No raw secret or credential-bearing header is included.

Run `python summarize_runs.py` offline to check retained response hashes, recompute usage costs/strict scores and regenerate `execution-report.json`. Inference responses include refusals/truncation/invalid records; pre-inference failures remain separate attempts with unknown costs. `completion_strings` counts content-bearing responses separately. All available observations and matched-repeat comparisons are both reported.

## Fixed-model results

Model: `gpt-4.1-mini-2025-04-14`, temperature 0, top_p 1, n 1, max_completion_tokens 1000, service_tier default, store false, no tools/history/retrieval/retries. The same full task/schema/source URL is used across arms; the oracle is withheld. The complete 60-job plan is in the ledger. Missing inference responses are offline links/Markdown repeat 0 and offline catalog/text repeat 0; matching repeat labels therefore leave four comparable rounds for those cases.

| Matched input | Repeats per arm | HTML accepted | Markdown accepted | Text accepted |
|---|---:|---:|---:|---:|
| Same-capture catalog | 4 | 4 | 0 | 4 |
| Same-capture links | 4 | 4 | 4 | 0 |
| Same-capture attributes | 5 | 5 | 0 | 0 |
| Saved hosted catalog | 5 | 5 | 0 | 0 |

All 58 inference responses completed with stop: 28 accepted pages and 30 incorrect pages. Twenty-five incorrect responses were `[]`; five attribute/Markdown responses omitted both required SKUs. We do not pool unlike cases into a format ranking. Nominal 95% Wilson repeat intervals assume independent Bernoulli responses, which repeated identical inputs may violate; they do not establish coverage across websites or production reliability.

Reported usage: 48,709 input tokens (14,976 cached), 4,860 output tokens. Published standard token rates yield known usage cost US$0.0227668. Including both unknown-charge reservations gives US$0.0299668 allowance accounting under the US$0.25 ceiling. Actual all-attempt billing is unknown. Cells with zero accepted pages have undefined cost per accepted output; cells containing unknown-charge attempts keep all-attempt cost ratios null. Other cells report per-accepted-page token-rate cost. Caching/order and success-dependent output lengths mean these costs do not isolate a format-size effect. The report retains every cell, usage record, system fingerprint and score.

Hosted text differs from local browser selection and failed this fixed task despite preserving all required literals. This is observed model behavior, not a causal explanation of which text difference mattered. The saved-output model phase does not test interactive agent planning, acquisition retries or a production workflow. No paying-customer impact is measured.

The blog remains `draft: true`. Oleg Kulyk must review conclusions, method and byline before any publication; AI execution and independent AI evidence review do not imply human review. No source merge, deployment or Terraform is authorized here.
