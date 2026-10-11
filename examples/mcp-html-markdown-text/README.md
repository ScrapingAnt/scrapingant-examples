# HTML, Markdown or plain text for one extraction contract

This packet backs the draft article “HTML vs Markdown vs Plain Text for LLM Extraction.” It demonstrates field information loss and content token counts on frozen inputs. **It does not contain measured LLM accuracy or authenticated live MCP retrieval results.** No new paid calls were made. See [PROTOCOL.md](PROTOCOL.md) for the proposed bounded model/live phase and missing approval/access.

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

Pending separate explicit approval: at most 15 static-fixture MCP retrieval calls / documented 15-credit ceiling and at most 60 GPT-4.1 mini calls / US$0.25 ceiling. Both secure keys are absent in this environment. No live paid runner is supplied or silently invoked. Exact observed MCP credit receipts are unavailable from the inspected content-only tool result; do not turn a documentation estimate into a measured bill.

The blog remains `draft: true`. Oleg Kulyk must review conclusions, method and byline before any publication; AI execution and independent AI evidence review do not imply human review. No source merge, deployment or Terraform is authorized here.
