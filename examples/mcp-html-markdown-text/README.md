# HTML, Markdown or plain text for one extraction contract

This packet backs the draft article “HTML vs Markdown vs Plain Text for LLM Extraction.” It demonstrates field information loss and content token counts on frozen inputs. It also retains15 authenticated hosted MCP retrievals and their scoped account-counter observations. **No LLM accuracy result exists:** the first approved model attempt returned 401 invalid_api_key and stopped without retry/completion/usage. See [PROTOCOL.md](PROTOCOL.md) for completed work, the retained failure and remaining access gate.

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

The same fixed schema is used for all cases: name, displayed price, units sold, share, SKU, buy URL. Seven unique fixture records are reused; five local transformations are not five new sites or records. No accuracy/credit/cash-cost winner is claimed.

## Optional public schema discovery

```bash
python discover.py
```

This makes three read-only unauthenticated requests to the existing hosted MCP endpoint and replaces the saved discovery observation. Do not run it as part of strict offline replay. It reads no credentials and cannot call a retrieval tool. Do not confuse transport discovery with an extraction run.

## Paid phase and publication

Fresh approval: at most15MCPattempts/15 credits and60 fixed-model attempts / US$0.25. All 15 MCP attempts completed; account counters increased 15 in total, without per-call receipt/exclusive attribution. Model attempt 1failed authentication; its US$0.0036 reservation is retained, actual cost unknown,59 attempts remain. Existing credential routes were approved; no new credentials/accounts/purchases were created.

`mcp_live.py` and `model_run.py` require explicit execution flags and keys supplied securely in the environment. They are not called by `run.sh`. Do not rerun them against a paid account without a fresh bounded approval. Each run requires a fresh directory; no retries or stopped-run resumption. An account selection override must not silently choose another provider. The supplied model runner expects a complete 15-call live directory; it does not automatically continue this failed execution.

`expected_output/live-mcp-2026-10-11/` retains all 15 requests/responses/outputs and authenticated discovery. `expected_output/live-model-2026-10-11/` retains the failed request and sanitized 401 response. `execution-report.json` separates content preservation/tokenization, hosted acquisition and absent model outcomes. Run `python summarize_runs.py` offline to validate capture hashes and recompute that report. Account absolute counters/internal period identity and the provider's masked credential identifier are omitted from public copies; no model billing receipt/zero charge is inferred.

The blog remains `draft: true`. Oleg Kulyk must review conclusions, method and byline before any publication; AI execution and independent AI evidence review do not imply human review. No source merge, deployment or Terraform is authorized here.
