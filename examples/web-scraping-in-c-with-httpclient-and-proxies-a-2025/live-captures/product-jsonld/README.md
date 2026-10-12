# Native owned-product full-client capture — 2026-10-12

One real rendered `/v2/general` request passed the public `ManagedClient.FetchAsync`
path with explicit `SingleProductOfferJsonLd`: request construction/send, target/type
checks, native field parsing and credit receipt acceptance. The target is the existing
[owned synthetic product](https://scrapingant.github.io/scrapingant-examples/fixtures/apify-continuation-v1/commerce/product-000.html),
from fixture commit `0d0ccf1b230d8548217b4fdebb5b22a47786cc9f`.
It says "SYNTHETIC, no live store or sale"; no real-store coverage is claimed.

The public client source used by the call is commit
`b24cddeaaad174c6b11679a61fedaf7197f87960`, with `ManagedClient.cs` SHA-256
`0738d9d197acb5f1268326f85186e52be7bc2f549299112b1e31caa85478d1f7`.
That executed source remains the historical live-call pin. The current packet adds
only a three-character currency length guard to the default ArticleFields parser;
the native JSON-LD path is unchanged. Its corrected `ManagedClient.cs` SHA-256 is
`f6da3e2c175a5e72c674cb39fcda45a7285077deb232b867212e178e0b3735a7`.
The corrected client replays the saved native bytes offline;
no live request was repeated. A separate one-dispatch observer invoked the public
method at the historical pin, buffered received bytes unchanged and saved them
after the client and an independent four-field literal oracle accepted the result.
The observer and credential binding are not included in this public packet.

The selected contract requires one native `application/ld+json` script containing a
top-level Product with `https://schema.org` context, one Offer object and string
SKU/name/price/currency values. It rejects ambiguous scripts/properties, arrays,
graphs and missing/invalid fields. It does not rewrite the page into ArticleFields
or automatically fall back to another schema. The original ArticleFields default
remains available.

## Actual observation

HTTPS GET used the `x-api-key` header, `browser=true`, `timeout=30`,
`proxy_type=datacenter`, `proxy_country=us`, and `return_page_source=false`.
There was no selector wait, redirect, retry, model/extractor or account/usage call.
The caller deadline was 95 seconds, with maxAttempts=1 and a one-dispatch observer
guard. The observer capped bytes at 1 MiB; the public client retained its existing
1,048,576-character cap. A declared media type is checked when present.

| Observation | Actual value |
|---|---|
| UTC start → finish | 2026-10-12 09:03:48.7752780 → 09:03:50.9011750 |
| Elapsed time | 2125 ms, one observation rather than a benchmark |
| API / target status | 200 / 200 |
| Requests / client attempts | 1 / 1 |
| Actual credit receipt | 10 credits |
| Original target / outer media type | text/html / text/html |
| Product | SYNTH-000 / Synthetic product 000 / decimal 12.34 / USD |
| Saved response | 601 bytes |
| Public live CLI executed | false |
| Real store validated | false |

Response SHA-256:
`169b93ff2cfc5e750ae4cfe1f209766a63beb2f1d0d4eddc32fe7b8945d73695`.
`receipt.json` contains the 24 allowlisted result fields, including the actual receipt
and validated product; `response.html` contains the exact accepted response bytes.
Raw request/header logs and credentials are absent.

The prior unauthenticated direct source GET returned 588 decoded entity bytes, SHA-256
`7c091cea8ce4b224709e8cc978a79b0c51d7294b68d62afd538d887bc7d43dcd`.
They exactly matched the existing fixture. `source-response.html` and selected
`source-receipt.json` retain that provenance; its raw Content-Length header describes
the wire response, not the decoded byte count. The full documents differ, while their
native JSON-LD script text is identical. No transformation into the attribute-based
catalog schema was introduced.

## Offline replay

From the packet directory:

```bash
python3 live-captures/product-jsonld/verify_capture.py
python3 live-captures/product-jsonld/verify_capture.py --controls
```

The Python 3.12.11 standard-library replay checks exact hashes/byte counts, single
request/attempt, statuses, actual receipt and flags, unchanged native script, and
literal SKU/title/decimal price/currency in `oracle.json`. Eight corruption controls
reject modified bodies, wrong/unknown receipts, wrong fields and broadened client/CLI/
store claims. It reads no key and makes no request. `./run.sh` includes this replay,
the historical marker replay, 59 default client cases and 62 separate native
contract/CLI cases. All handlers in those executable checks are fake.

This capture establishes full public-client acquisition on one owned synthetic
Product/Offer fixture. It does not establish arbitrary JSON-LD, real catalogs,
production performance/reliability, anti-bot behavior or plan capacity. Static JSON-LD
already contains the fields in the direct source; this request does not establish
JavaScript-driven product updates. The separate October 11 delayed-marker captures
cover that owned page's dynamic behavior. The public live CLI remains illustrative
and unexecuted. Named-author review and publication approval remain pending.
