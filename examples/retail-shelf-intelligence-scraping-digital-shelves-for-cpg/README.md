# Selected retail SKU observations

Runnable evidence for the [retail shelf article](https://scrapingant.com/blog/retail-shelf-intelligence-scraping-digital-shelves-for-cpg).
One fixed Adagio product-page contract selects the 3oz and 16oz weight offers by
product group, SKU and size. The two offers share a URL. The collector preserves
leading zeroes in IDs and leaves `variant_id` null because the inspected source
has no separate variant-ID field.

## Run the offline packet

Use CPython **3.12.11**, pinned in `.python-version`. No pip packages are required.
Run from this directory with that interpreter on your PATH:

```bash
PYTHON=python3 ./run.sh
```

Or set `PYTHON` to your CPython 3.12.11 executable. `run.sh` verifies the runtime,
runs the scoped suite against owned loopback/in-memory responses, checks six
behavior mutations, and captures actual local CLI JSON, CSV and summaries in
`expected_output/`. The runner has no external, provider or model operation even
if `SCRAPINGANT_API_KEY` is present. Its test process rejects external DNS/socket
attempts. Child CLI replays read local files only. The separate PR workflow pins
3.12.11 and invokes this offline runner without secrets; the repository's monthly
workflow and allowlist are unchanged.

The fixture timestamps are controlled inputs, not fresh retailer observation times.
These individual commands were also exercised by the runner:

```bash
python3 collector.py replay fixtures/baseline.html --observed-at 2026-10-13T11:00:00Z
python3 collector.py replay fixtures/changed.html --observed-at 2026-10-13T12:00:00Z
python3 collector.py replay fixtures/partial.html --observed-at 2026-10-13T12:00:00Z
python3 collector.py replay fixtures/changed-pack.html --observed-at 2026-10-13T12:00:00Z
python3 collector.py projection fixtures/adagio-field-projection.json
```

Partial/failed collection returns exit 1 while still emitting accepted records
and rejection reasons. Invalid input or a missing managed credential returns 2.
The driver deliberately expects exit 1 for the partial and changed-pack controls.

## Read the observations

Every accepted record carries product group, SKU, literal size, weight quantity
and unit, decimal price string, explicit currency, availability, observation UTC,
requested and observed source URLs, offer/market/fulfilment context and bounded
field evidence. `pack_unit=ounce` is a weight measure; it does not represent
teabag count, liquid volume or a general pack converter. Only exact selected
`3oz` and `16oz` sizes are accepted. A changed pack fails the existing contract
and requires a separately reviewed selection update.

Price is the selected `ProductGroup.hasVariant[].offers.price`, never the
aggregate sample/from price. A single `Offer` and explicit USD are required.
Missing, duplicated, conflicting or malformed selected records make acquisition
partial/failed. An HTTP/API/target 200 alone cannot accept the field record.

Only explicit schema.org InStock/OutOfStock values become `in_stock`/`out_of_stock`.
Missing or unrecognized availability is `unknown`. A failed page or absent SKU
has no availability record. Transitions to/from unknown are field observations,
not asserted stock-in/out events.

`market=US` requires actual page microdata inside `shippingDestination` with
`addressCountry=US`; otherwise it is unknown. This is page shipping context,
not a guaranteed proxy location or selected checkout destination. Fulfilment
stays `unselected`, purchase basis `unspecified`, and offer kind
`listed_variant_offer`. Optional auto-delivery discounts are excluded.

`changes.json` compares only matching group/SKU/size/pack/currency/source/offer
context. A context change appears as a new, incomparable observation. Omitted
records remain in `unobserved_prior_records` with their original timestamps.
Even a complete two-offer acquisition makes no retailer-inventory disappearance
claim. Older or duplicate snapshot identities are rejected.

## Source evidence and optional retrieval

The direct public source inspection on October 13, 2026 supplied two minimal
factual offers, independently typed source oracles and field selectors. Only
those facts and provenance are distributed. The original HTML stays private;
its body hash cannot be regenerated from the field projection. Projection
replay validates saved fields and creates no fresh HTTP/managed receipt.
The fictional Riverline fixture data are independently authored controls,
not a retailer capture. The full source's unrelated descriptions, reviews,
images, scripts, sample and teabag offers are outside the selected workload.

Direct HTML already contained the selected facts, so ScrapingAnt is optional.
The following commands make network requests and are **excluded from run.sh**:

```bash
python3 collector.py direct
python3 collector.py managed --browser false
```

Both target only the fixed Adagio URL, not arbitrary retailers. The optional
managed CLI reads an existing `SCRAPINGANT_API_KEY` environment binding and sends
it in the `x-api-key` header, outside logged URLs. `--browser true` explicitly
selects rendering; it is not used as an automatic retry. Both modes set
`proxy_type=datacenter`, `proxy_country=us`, `return_page_source=false` and
`timeout=30`. There are no API redirects, retries, fallback, residential escalation,
account usage/status calls.

The transport uses a 30-second socket timeout and elapsed read checks, plus a
262,144-byte body cap. These checks are not a hard 30-second wall-clock guarantee:
a blocking read can finish after the elapsed threshold before the next check.
API redirect rejection does not prove the provider avoided redirects on the
remote target. API status, `Ant-page-status-code`, original target media type
and `Ant-credits-cost` are read separately. Missing/malformed credit evidence
remains unknown, never zero. Credit receipt cost is retained even if no field
record is accepted; per-accepted-record cost has no value when the denominator
is zero or actual credits are unknown. Managed test headers are in-memory
controls, distinct from the separately recorded billed observation below. The CLI prints no received HTML, raw headers
or credential data. See the [response documentation](https://docs.scrapingant.com/request-response-format)
and [credit receipt documentation](https://docs.scrapingant.com/credits-cost).

## Recorded managed observation

On October 13, 2026, one separately recorded raw managed validation request ran the frozen
`acquire()` and `collection()` code. API and target both returned 200 with HTML,
one actual receipt credit and two accepted observations: group `001036`,
SKU `001036002` / `3oz` / `9.00 USD` / explicit out-of-stock, and
SKU `001036004` / `16oz` / `29.00 USD` / explicit out-of-stock.
The receipt's observation time is `2026-10-13T10:59:39.348080+00:00`.
The observed credit cost per accepted record is `0.50` for that one request,
not a forecast for retailer coverage or repeated collection.

`expected_output/managed-2026-10-13/` contains the unaltered safe receipt,
bounded field collection and execution provenance. The received 87,942-byte
body has hash `1e64467b5c69879349facba7c62c8e3d3a86a9e9d2e44454bc4f3c56a3b14473`;
its bytes are withheld. It differs from the earlier direct body's hash, while
selected fields match the independently typed source oracle. Managed DOM
corroboration covers size and out-of-stock labels; gram secondary labels seen
in the earlier direct capture were absent in this response.

After this capture, projection-replay validation was tightened to reject
contradictory capture times, hashes, source kinds and material fields. The
receipt retains the exact executed code hash and points to
`validation/raw-call-collector.py`, an unchanged audit-only source snapshot.
That snapshot is excluded from default tests, replay commands and the current
CLI; use `collector.py` for the supported interface. Native HTTP acquisition
and valid-source field extraction remain unchanged.
The current collector rejects malformed HTMLParser marked sections as incomplete
observations; saved-projection validation and locator mapping were strengthened after capture. A local replay of the retained
genuine bytes under the final validator produces the same two records; no
provider call is needed for that check. The separate direct projection requires
consistent explicit UTC capture time, SHA256, direct-source kind and exact
identity/weight/offer context across both saved facts.

The standalone public managed CLI was not invoked. The default runner reads
these saved records locally and verifies their fields; it never repeats the
paid request. No rendering, managed refresh, source-wide yield, inventory or
JavaScript requirement follows from this one raw observation.

## Evidence files and limits

- `fixtures/baseline.html`, `changed.html`, `partial.html`, `changed-pack.html`:
  owned small structural pages and independent literal record oracles.
- `fixtures/adagio-field-projection.json`, `adagio-source-oracle.json`,
  `adagio-field-contract.json`: minimal factual source projection, independent
  inspection oracle and fixed selectors.
- `expected_output/baseline.json`, `changed.json`, `partial.json`, `changed-pack.json`:
  captured CLI output; `records.csv` contains the baseline's two rows.
- `expected_output/changes.json`, `partial-changes.json`, `changed-pack-changes.json`:
  conservative reports; `naive-price.json` captures aggregate-price misassignment.
- `expected_output/adagio-projection-replay.json`, `adagio-projection-records.csv`:
  saved-fact replay, distinct from live HTML acceptance.
- `expected_output/tests.txt`, `negative-controls.txt`, `tdd-*.txt`, `summary.txt`:
  actual verification output. TDD files retain captured result summaries and
  withhold local failure traces.
- `expected_output/managed-2026-10-13/`: separately recorded real raw receipt,
  minimal field collection and frozen execution provenance; full body withheld.
- `validation/raw-call-collector.py`: exact audit-only executed source bytes,
  excluded from the default runner and current CLI.
- `evidence.yaml`: dated claims, denominators, executed scope and limitations.

This is one selected two-offer source contract. It supplies no universal SKU
matching, source-wide coverage, checkout/inventory validation, scheduler,
production yield, digital-shelf analytics or revenue result. The default runner
never reruns a paid observation. Named-author methodology review and final
publication approval remain pending; no human review report is asserted.
