# MCP retrieval → model extraction → validated records

**Status, September 30, 2026: real retrieval complete; model extraction blocked by provider quota. Not an executed AI extraction demonstration or publication-ready article.**

The owner authorized ScrapingAnt fetches and up to $10 of OpenAI model spend. Five sequential `get_web_page_markdown` calls succeeded on owned synthetic fixtures, with `browser=false` and `proxy_type=datacenter`. The first OpenAI generation returned HTTP 429, `insufficient_quota`; execution stopped without retries. There are no generated records or model-quality results. A successful credential/model-list check did not establish generation quota.

## Reproduce offline

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.lock.txt
./run.sh
```

`run.sh` performs 22 injected/offline checks and scores the saved attempt ledger. It never calls either provider, even if credentials are configured. Null rates mean there were no model-emitted records to score, not zero accuracy. `expected_output/live-2026-09-30/` preserves discovery, five raw MCP envelopes, five Markdown files and hashes, the failed model attempt, and the replay report. Empty accepted/quarantine files mean no model response was received, not that every source record was accepted.

## Fixtures and independent scoring

Five HTML fixtures cover a complete two-product catalog, changed wrappers/classes with identical values, missing price, contradictory price/currency, and a page instruction to fabricate records. Public copies are in `fixtures/mcp-catalog/` at repository commit `dbf3261c7d3960558ba52fa200f8136e9da28bb2`. The experiment fetched immutable raw GitHub URLs, not a changing branch. Static HTML needs no JavaScript rendering in this test.

`schema.json` defines the application record contract. The pinned prompt and schema are sent to the model together with the saved Markdown and its source URL. `oracle.json` is independently authored scoring data and is never included in a model request. The model has no tools or network access.

`validate.py` rejects malformed JSON, extra keys, wrong types, duplicate IDs, invented values, incorrect source URLs and unsupported excerpts. Null fields can conform to the schema while still requiring quarantine. Exact excerpt membership is checked against the saved Markdown; whitespace is normalized only when comparing the excerpt to the oracle's supporting statement. This fixture oracle is test infrastructure, not an automatic fact checker for arbitrary websites.

Metrics deliberately separate schema conformance, oracle value accuracy, and acceptance. Value precision is unique schema-valid oracle-matching records / all emitted records; recall is those matches / expected fixture records across completed runs. Correct null reporting can match the oracle but remains quarantined. Complete-run success requires every expected record accepted, with no errors, omissions or quarantine, divided by all attempted model runs. Synthetic failure controls are injected tests, not observed provider behavior.

## Explicit live stages

Provide `SCRAPINGANT_API_KEY` and `OPENAI_API_KEY` through your shell's secret mechanism. No keys belong in this repository. Use a new output directory for each attempt; existing ledgers are never overwritten.

```bash
python live.py retrieve --output /tmp/mcp-new-retrieval \
  --fixture-commit dbf3261c7d3960558ba52fa200f8136e9da28bb2
MODEL_BUDGET_USD=10 python live.py extract --output /tmp/mcp-new-retrieval
python replay.py --capture /tmp/mcp-new-retrieval --write /tmp/mcp-new-retrieval
```

After fixing OpenAI billing/quota, **reuse the saved successful retrievals** without fetching again:

```bash
MODEL_BUDGET_USD=10 python live.py extract \
  --retrieval-capture expected_output/live-2026-09-30 \
  --output /tmp/mcp-model-resume
python replay.py --capture /tmp/mcp-model-resume --write /tmp/mcp-model-resume
```

The runner pins `gpt-4.1-mini-2025-04-14`, temperature 0, JSON-object mode and at most 2,000 completion tokens per attempt. It makes three repetitions per successful fixture, sequentially, with no repair/retry loop. JSON-object mode is not schema enforcement; validation happens locally. The input prompt plus source is bounded to 24,000 UTF-8 bytes. The reviewed runner conservatively reserves the full 1,047,576-token model context per request, covering message framing as well as content. Standard list prices checked September 30 at [OpenAI's model page](https://developers.openai.com/api/docs/models/gpt-4.1-mini) are $0.40 input / $1.60 output per million tokens. The current per-attempt reservation is $0.4222304; fifteen reservations total $6.333456, below the authorized $10 ceiling. The first rejected attempt predates this conservative accounting revision and records its original $0.0128 reservation. These are conservative planning limits, not a bill. Actual usage is recorded only when returned; aggregate usage/cost remains unavailable if any attempt lacks usage. ScrapingAnt credits were not exposed in these MCP envelopes, so credit cost is recorded as unavailable.

## Limits and provenance

This packet does not establish production reliability, autonomous navigation, layout robustness beyond one fixture, general prompt-injection resistance, or extraction quality: no successful model generation exists yet. Prior `expected_output/discovery.json` is the September 29 discovery-only preparation; dated live captures are separate. An initial runner import error was fixed before network execution. Python 3.12.11 and exact dependencies/input hashes are recorded in `expected_output/environment.json` and `requirements.lock.txt`.
