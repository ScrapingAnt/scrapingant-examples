# MCP retrieval → model extraction → validated records

**Executed September 30, 2026:** five MCP retrievals and 15 Anthropic model extractions, with all raw responses retained. The earlier OpenAI attempt failed for insufficient quota and remains recorded separately.

The owner authorized the Anthropic key in place of OpenAI, with the existing $10 model-spend ceiling. `claude-haiku-4-5-20251001` completed all 15 calls on the five saved MCP results; no additional fetches or model retries were made. Reported usage was 9,228 input and 4,632 output tokens, corresponding to $0.032388 at standard list prices, not a billing receipt.

All 15 model messages enclosed their JSON in a Markdown fence, despite the prompt requesting only JSON. Strict raw JSON parsing therefore failed 15/15. The reviewed offline framing decoder accepts either raw JSON or exactly one complete `json` fence; it rejects surrounding prose, multiple fences and incomplete fences. It removes only that wrapper, never searches for an object or repairs values. Each result records this framing decision. With framing decoded, 30/30 records conform to the schema and match oracle values, 24 are accepted and six are quarantined for missing/ambiguous price/currency. Correct null reporting counts as value accuracy but does not make a record safe to store. Nine of 15 runs accept every expected record; the other six intentionally quarantine one unavailable/ambiguous record. These are five small fixture cases, not a production accuracy benchmark.

## Reproduce offline

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.lock.txt
./run.sh
```

`run.sh` performs 27 injected/offline checks and scores the saved Anthropic responses. It never calls either provider, even if credentials are configured. `expected_output/anthropic-2026-09-30/` contains the 15 original Messages API responses with run IDs/usage, reused MCP captures, `validation.json`, `accepted.jsonl` and `quarantine.jsonl`. `expected_output/live-2026-09-30/` preserves the original five retrievals and the rejected OpenAI attempt; its quality/usage rates remain unavailable. None of the injected failure controls or mock API responses are stored as live observations.

## Fixtures and independent scoring

Five HTML fixtures cover a complete two-product catalog, changed wrappers/classes with identical values, missing price, contradictory price/currency, and a page instruction to fabricate records. Public copies are in `fixtures/mcp-catalog/` at repository commit `dbf3261c7d3960558ba52fa200f8136e9da28bb2`. The experiment fetched immutable raw GitHub URLs, not a changing branch. Static HTML needs no JavaScript rendering in this test.

`schema.json` defines the application record contract. The pinned prompt and schema are sent to the model together with the saved Markdown and its source URL. `oracle.json` is independently authored scoring data and is never included in a model request. The model has no tools or network access.

`validate.py` rejects malformed JSON, extra keys, wrong types, duplicate IDs, invented values, incorrect source URLs and unsupported excerpts. Null fields can conform to the schema while still requiring quarantine. Exact excerpt membership is checked against the saved Markdown; whitespace is normalized only when comparing the excerpt to the oracle's supporting statement. This fixture oracle is test infrastructure, not an automatic fact checker for arbitrary websites.

Metrics deliberately separate schema conformance, oracle value accuracy, and acceptance. Value precision is unique schema-valid oracle-matching records / all emitted records; recall is those matches / expected fixture records across completed runs. Correct null reporting can match the oracle but remains quarantined. Complete-run success requires every expected record accepted, with no errors, omissions or quarantine, divided by all attempted model runs. Synthetic failure controls are injected tests, not observed provider behavior.

## Explicit live stages

Provide `SCRAPINGANT_API_KEY` and `ANTHROPIC_API_KEY` through your shell's secret mechanism. No keys belong in this repository. Use a new output directory for each attempt; existing ledgers are never overwritten.

```bash
python live.py retrieve --output /tmp/mcp-new-retrieval \
  --fixture-commit dbf3261c7d3960558ba52fa200f8136e9da28bb2
MODEL_BUDGET_USD=10 python live.py extract --provider anthropic --output /tmp/mcp-new-retrieval
python replay.py --capture /tmp/mcp-new-retrieval --write /tmp/mcp-new-retrieval
```

**Reuse the saved successful retrievals** without fetching again:

```bash
MODEL_BUDGET_USD=10 python live.py extract --provider anthropic \
  --retrieval-capture expected_output/live-2026-09-30 \
  --output /tmp/mcp-model-resume
python replay.py --capture /tmp/mcp-model-resume --write /tmp/mcp-model-resume
```

For Anthropic the runner pins `claude-haiku-4-5-20251001`, temperature 0, thinking disabled by omission, and at most 2,000 output tokens. It makes three repetitions per successful fixture sequentially, with no repair/retry loop. Prompt instructions do not enforce JSON formatting or schema conformance; decoding and validation happen locally. The original OpenAI provider remains available for historical reproducibility but was not used after its quota rejection.

Input prompt plus source is capped at 24,000 UTF-8 bytes. Anthropic reservations conservatively cover its entire documented 200,000-token context plus 2,000 output tokens: $0.21 per attempt, $3.15 for fifteen attempts, below $10. Standard prices checked September 30 at [Anthropic's model overview](https://platform.claude.com/docs/en/models/overview) are $1 input / $5 output per million tokens. API responses report zero cache-write and cache-read tokens for this capture. The earlier OpenAI rejection records its original $0.0128 reservation; its subsequently reviewed runner reserves $0.4222304 per attempt. Reservations are planning limits, not bills. Usage is recorded only when returned; aggregate usage remains unavailable if any attempt lacks it. ScrapingAnt credits were not exposed in the MCP envelopes, so credit cost is unavailable.

## Limits and provenance

This packet does not establish production reliability, autonomous navigation, layout robustness beyond one fixture, general prompt-injection resistance, or accuracy on unseen sites. All repeated cases are small synthetic catalogs, not independent samples of the web. Prior `expected_output/discovery.json` is the September 29 discovery-only preparation; dated live captures are separate. An initial runner import error was fixed before network execution. Python 3.12.11 and exact dependencies/input hashes are recorded in `expected_output/environment.json` and `requirements.lock.txt`. Model prompt/schema hashes and provider settings are recorded alongside each dated model ledger.
