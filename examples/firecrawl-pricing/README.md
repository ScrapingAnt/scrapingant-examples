# Firecrawl pricing: accepted-output evidence and offline budget model

This packet accompanies a ScrapingAnt-published pricing guide. ScrapingAnt is a competing retrieval API. It contains no ScrapingAnt comparison run and makes no provider ranking claim.

## What was observed

On October 1, 2026, the study made 200 billed basic-proxy retrievals: 24 exploratory pilot calls and 176 preregistered calls. All requested Markdown and HTML, without AI extraction or premium formats. Each returned result reported one credit. These were free credits; no cash expenditure was measured. One additional connector-catalog rejection happened before transport and had a separately verified zero debit; its reported-credit field is absent, not inferred.

Six owned synthetic fixtures and one nonexistent path shared one GitHub Pages origin. The pinned fixture revision is [6e747492b7f81ff999439374d40aeb7d00e34f65](https://github.com/ScrapingAnt/scrapingant-examples/tree/6e747492b7f81ff999439374d40aeb7d00e34f65/fixtures). `sources/manifest.json` pins exact source bytes. Ordinals in this packet are local study rows, not provider request identifiers.

The expansion had eight settings × 14 fresh slots, 32 delayed-pair calls, 16 permanent-404 diagnostic calls and 16 fresh/cache calls. `data/design.json` preserves the dated design and schedule. Default delayed requests omitted `waitFor`; corrective second calls used 2500 ms. Fresh calls used `maxAge=0`. Cache repeats allowed 3600000 ms and `storeInCache=true`.

## Run offline

Python 3.10 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
./run.sh
```

Dependency installation needs package access. Replay, acceptance checks and budgeting use stored files only, require no credentials and make no network or provider calls, even if keys exist in the environment. Do not run a live provider command to reproduce these calculations.

`data/captures.jsonl` retains exact output strings and only allowlisted request settings and response metadata. `data/attempts.csv` records 201 attempts and effective debits. Account data and connector envelopes are excluded. `score.py` reproduces `expected_output/ledger.csv`, `summary.json` and `replay.txt` from stored outputs using source-grounded `acceptance.py` checks. Input hashes are in `data/manifest.json`.

Expected replay:

```text
Offline replay: 200 billed calls, 200 credits; 24 pilot + 176 preregistered; 201 connector attempts.
delayed-corrective-pair: 16 credits / 8 accepted = 2.0
delayed-same-pair: 16 credits / 0 accepted = undefined
Eight balanced settings: 14/14 basic preservation per setting; stricter contracts reported separately.
```

## Use the budget model

The current monthly USD plan and $5 top-up inputs were checked on October 2, 2026 against [official pricing](https://www.firecrawl.dev/pricing) and its [public Markdown document](https://www.firecrawl.dev/pricing.md). `data/prices.json` records these documented inputs. Annual billing is excluded from the model. Taxes, other endpoints, add-ons, existing purchased credit balances and operational costs are excluded. This is a new-period allowance model, not an invoice forecast for an existing account.

```bash
python3 budget.py --plan Standard --urls 1000 --runs 30 --retry-attempts 0 --credits-per-attempt 1 --accepted 27000
```

This hypothetical workload needs 30,000 credits. The model returns $99, 70,000 unused plan credits and approximately $0.00367 per accepted output. The 27,000 denominator is a user-supplied scenario, not a measured acceptance rate. Retries increase attempts; they do not create additional scheduled unique outputs. For zero accepted outputs, JSON `null` means the ratio is undefined. To compare selected plans, run the same scenario with another `--plan`; the script does not pick a plan or model concurrency.

## Contracts and limits

A basic retrieval-preservation pass does not mean an application accepts the result. Missing-price output preserves missingness but fails a two-numeric-prices requirement. Delivered 404s pass recognizable-error diagnostics and provide no requested content. Complex table HTML preserves 12 table structures, including the nested table; the stricter visible-only Markdown contract rejects the hidden row. Pipe Markdown has no native rowspan/colspan syntax. No universal provider visibility guarantee or provider-specific defect follows.

Eight corrective pairs accepted eight delayed outputs after failed first calls: 16 credits / 8 = 2 each. Eight same-setting pairs accepted zero: the ratio is undefined. Fresh/cache tests used unchanged source content; they do not prove freshness after an edit. Repeated sequential requests on one origin/account/session are not independent production trials. Do not pool these deliberately different checklists into overall accuracy. No production anti-bot, SLA, throughput, engine timing, AI extraction or head-to-head test was run. Missing receipt and API HTTP-status fields remain unknown.

## Visual provenance

`render_visuals.py` uses the actual saved outputs, not AI-generated evidence. `visuals/credits-data.csv` derives separate subset numerators and denominators. `delayed-render.html` faithfully renders saved outputs 56 and 57. `table-render.html` renders the exact two-row header from output 36 beside its unchanged Markdown text; display CSS is added. These are offline presentations of saved output, not screenshots taken during the retrieval calls. `banner.png` is editorial title artwork.

Optional visual regeneration requires the separately pinned Playwright dependency and its Chromium browser:

```bash
python3 -m pip install -r visuals-requirements.txt
python3 -m playwright install chromium
python3 render_visuals.py
```

The rendering context blocks HTTP/HTTPS. Browser installation needs ordinary download access; visual rendering itself makes no network or provider calls. Adjacent article captions and tables give text equivalents. AI agents assisted with export code, offline analysis, prose, figures and automated editorial/factual review. No separate human review is claimed.
