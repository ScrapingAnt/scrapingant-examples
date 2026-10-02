# Apify pricing: offline charge-reconciliation worksheet

This is a parameterized **calculation worksheet**, not an Apify runtime benchmark. All seven ledgers are **synthetic**, including Actor IDs, versions, resource quantities and accepted-record counts. No Actor was run to produce these examples. They are not customer invoices, observed consumption or evidence of savings.

Official monthly prices and billing rules were checked **2026-10-02**. Python **3.10.2 and 3.12.11** were tested. Default execution uses only the standard library, no credentials, network access, dependencies or provider calls. The package is published by ScrapingAnt, which sells a competing retrieval API. It contains no comparison of provider performance or economics.

## Reproduce

Download this versioned folder or clone the examples repository and enter `examples/apify-pricing`. From that folder:

```bash
./run.sh
python3 model.py fixtures/s2-event-plus-usage.json --csv /tmp/apify-s2-lines.csv
python3 model.py fixtures/s4-missing-usage.json --csv /tmp/apify-s4-lines.csv
```

The first command runs **38 tests**, verifies **15 JSON/CSV output files for seven synthetic scenarios**, and checks **three deterministic SVGs**. The other commands emit the model result as JSON and write inspectable line-item CSVs. `rated_amount_usd` is a resource valuation; `billed_amount_usd` is what this charging model adds to the buyer's eligible usage. Included run usage has a billed amount of zero, even if its memo valuation is positive. A blank CSV amount or JSON `null` is unknown, not zero.

To regenerate after deliberately changing an example or code, review the resulting diff:

```bash
python3 capture_examples.py
python3 make_visuals.py
./run.sh
```

Exit code 2 means invalid input. A valid but incomplete worksheet exits 0 with `status=partial`; inspect status and `unresolved` before using any total. The Free allowance can instead return `free_allowance_exceeded`, without a feasible bill or unit cost.

## Enter known charges

Copy `fixtures/worksheet-template.json`. Its quantities, prices and pricing model start unknown. Set `input_type=user_supplied` for supplied data and give it an accurate label. The worksheet cannot verify a user's billing data or validate an Actor's output for them.

1. Select a verified monthly USD plan and an explicit start/exclusive end covering one calendar month. There is no hidden 30-day multiplier. Annual/custom plans and partial cycles are not supported.
2. Supply one nonoverlapping scope per Actor, with ID, version/build, effective charging model and a dated official public pricing URL. Record effective event prices for the chosen plan, including any documented Actor-specific discount, and already **charged** event counts. Requested/produced events and accepted records are different quantities.
3. Supply cycle totals in provider meter units, or leave them `null`. `CU`, `GB`, `GB-hour`, `operation`, `SERP` and `request` are different units. GB-hours are integrated storage over time; counts of writes are not automatically dataset rows. There is no bytes-to-GB conversion or prediction from URLs, requested RAM, scheduled frequency, wall time or retries.
4. Choose `event_included`, `event_plus_usage` or `usage_only`. Only the first excludes Actor-run usage. Post-run storage/transfer is separately billable in all models. Unknown inclusion stays unknown. Rental is rejected rather than presumed migrated.
5. `other_account_usage_usd` is prepaid-eligible usage **outside these Actor scopes**, not the entire account usage repeated. `extra_cash_charges_usd` is a known total outside prepaid eligibility, excluding that other usage. Neither is an assumed price. Null/missing means the full account bill remains unknown.
6. List unresolved datacenter IP/add-on amounts, allowance treatment, direct third-party fees, credits/taxes/adjustments and limit feasibility in `unresolved_items`. An explicit empty list attests completeness. The code cannot detect the same measured units entered in both run/post-run scopes or in the other-account total.
7. Define an accepted-output unit, validation rule and count. Count complete, unique records under your own contract, retaining all charged attempts in the numerator. Zero or missing accepted output makes unit cost undefined. The example accepted counts are assumptions, not performance results.

All input numbers must be decimal strings or integers, never floats/bools. Negative/nonfinite values, fractional counts, wrong currencies/units/cadences, duplicate Actor/event scopes, duplicate JSON keys and unknown meter keys are rejected. Missing billable inputs leave a known subtotal and suppress a precise total. Missing included-run quantities are memo gaps only. Source metadata documents provenance; it does not automatically prove a supplied price is correct.

## Billing equation and applicability

With `W` these Actors' eligible charges, `O` other eligible usage, `A` account allowance, `F` plan fee and `X` known cash charges outside the allowance:

```text
eligible account usage = W + O
prepaid applied once = min(W + O, A)
paid-plan overage = max(W + O - A, 0)
cycle cash cost attributed = F + overage + X
incremental workload cash = max(W + O - A, 0) - max(O - A, 0)
workload usage per accepted output = W / accepted outputs
account cash per accepted output = cycle cash cost / accepted outputs
```

The subscription and its prepaid allowance are not two additive charges. Incremental workload cash assumes the same subscription is retained without the workload; it excludes that existing fee and extra cash. The full account bill per accepted output includes other usage/add-ons, so it is not workload marginal cost.

Paid overage is added to the **next invoice**. `cycle_cash_cost_usd` attributes the selected fee and that overage to the modeled cycle; it is not an invoice/payment-date prediction. Ordinary unused usage expires. Free's USD 5 allowance blocks service when exhausted rather than allowing paid overage. No renewal-date inference, plan-change proration, credits, taxes or actual invoice adjustments are performed. For incomplete paid-plan data, the known cash bound assumes nonnegative charges and no adjustments; it is not a reconciled invoice.

Raw decimal arithmetic retains subcent values, with 60-digit working precision. Display cents use one final `ROUND_HALF_UP`; **Apify invoice rounding is unverified**. Supplied CU must already be the applicable billed meter, including any conditional startup compute treatment; the worksheet does not subtract the documented free-start window again.

The only example event rate is the **configurable documented default** `apify-actor-start`: USD .00005 per event. Apify uses “synthetic event” for a platform-defined automatic event; this package uses “synthetic ledger” for invented test data. Charged start-event counts can depend on memory. These ledgers supply counts directly and do not imply that a real Actor has that rate, inclusion setting or workload. There is no generic price per result, automatic Store discount or best-plan recommendation.

## Synthetic examples and boundaries

All cases use explicit synthetic inputs. Each Actor's run meter valuation is USD **21.64**, its post-run eligible amount **.584**, and (where applicable) 960 charged default start events total **.048**. Thus inclusion changes which known quantities are added; it does not demonstrate different Actor efficiency.

| Synthetic scenario | Eligible workload charges | Modeled account cycle cash | Important distinction |
|---|---:|---:|---|
| S1 event price includes run usage | .632 | 19 | The 21.64 run valuation is a memo; prepaid unused 18.368. |
| S2 events plus run usage | 22.272 | 22.272 | Allowance 19, next-invoice overage 3.272. |
| S3 usage-only | 22.224 | 22.224 | No developer event charge. |
| S4 missing residential proxy quantity | Known subtotal 14.272 | Unknown | Cash bound 19 is not a precise bill; workload unit cost unknown. |
| S5 zero accepted records | 22.272 | 22.272 | Both accepted-output cost ratios are undefined. |
| S6 two nonoverlapping Actors + 15 other usage | 44.544 | 59.544 | Shared allowance applied once; overage 40.544. |
| S7 above Free allowance | 22.272 requested | Infeasible | Shortfall 17.272; no fictional paid overage estimate. |

The tests also cover allowance boundaries, subcent rounding, missing event prices/counts/sources, post-run transfers, other-account usage, outside-allowance cash, invalid units/currency/cadence, partial inputs, duplicate keys/scopes and accepted-output definitions. Hand-derived values in `test_model.py` are independent of the implementation. This proves arithmetic and serialization, not actual Actor event behavior, billing meters or acceptance rates.

## Sources, dates and visuals

`sources.json` records official URLs, public read dates/timestamps, body hashes and short verified excerpts; `rates.json` is the normalized monthly snapshot with per-1,000 divisors and explicit unsupported offers. Full third-party pages are not redistributed. Official sources:

- [Apify pricing](https://apify.com/pricing): plan/usage/resource tables and billing FAQ.
- [Actors in Store](https://docs.apify.com/actors/running/actors-in-store): models, post-run costs, rental sunset and optional Actor discounts.
- [Pay-per-event documentation](https://docs.apify.com/actors/publishing/monetize/pay-per-event): inclusion option, charged counts/limits and configurable start event.
- [Usage and resources](https://docs.apify.com/actors/running/usage-and-resources): meters, CU and historical dollar display limits.

The October 1, 2026 rental retirement is a **published schedule**, not this package's observation that every Actor migrated. Recheck a chosen Actor's actual model and effective-period rates. Current historical-run dollar displays are informational because they use current service prices; they do not establish a historical invoice.

`visuals/bill-flow.svg` is a rule diagram. `visuals/synthetic-costs.svg` uses the captured S1/S2 modeled amounts. Each SVG includes a title and description; the equations/table above provide text equivalents. `make_visuals.py` reproduces them without dependencies. The editorial banner is not a billing screenshot; optional `render_banner.cjs` uses Node 22.20.0 and `@resvg/resvg-js@2.6.2` to rasterize it. PNG is not a default arithmetic/CI dependency and font rendering can vary by system.

AI agents assisted with code, synthetic fixture preparation, documentation, visuals and automated calculation/factual review. ScrapingAnt is the publisher; Oleg Kulyk is the publication owner. No separate human review, customer evidence, realized savings or comparative superiority is claimed.
