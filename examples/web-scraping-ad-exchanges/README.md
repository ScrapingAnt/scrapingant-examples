# Check ads.txt declarations against sellers.json (offline)

Owned synthetic fixtures, not a market dataset or production IAB validator. The script does not fetch targets, call an API, follow variable directives, or use bid/impression/user data. All fixture companies, domains and relationships are illustrative, authored for this packet. No external source document is republished here.

## Reproduce

Recorded runtime: CPython 3.14.6 on macOS arm64. Python standard library only; no package installation or API key.

```bash
cd examples/web-scraping-ad-exchanges
./run.sh
```

Run a single report:

```bash
python3 check_declarations.py --format text
python3 check_declarations.py --format json
```

`run.sh` exits nonzero on failed assertions/commands, captures stdout in `expected_output/`, and records timestamp, runtime, local file SHA-256 hashes and successful step exit status in `run-meta.json`. Read `report.json` for the exact source filename, source body hash, ads line and zero-based seller-array index. No timestamps pretend to be HTTP retrieval times. A missing source has a null hash.

## Algorithm and interpretation

1. Ignore comment/blank lines and retain variable declarations separately without interpreting them. Parse only three/four-field data rows. Preserve IDs as strings; normalize only ASCII domain case and relationship/type enum case. Do not collapse subdomains or compare business and inventory domains.
2. Deduplicate the normalized `(advertising_system, seller_id, relationship, certification_id)` tuple. Retain each duplicate as a diagnostic referencing its first ads line; do not join it again.
3. Resolve the advertising-system domain through the explicit `fixtures/sources.json` local mapping. The synthetic fixture collection is explicitly declared complete; this is a teaching assumption, not a guarantee obtainable from an arbitrary HTTP response.
4. Reject the whole sellers input on unreadable bytes, malformed JSON, duplicate JSON members, unsupported spec version or invalid checked seller fields. The parser validates string seller IDs, case-insensitive seller types, integer confidentiality 0/1, public names, and type/nonempty value of present domains. It does not validate every optional spec field or domain's Public Suffix List.
5. Keep every seller record for each exact ID: zero records means absent in this complete fixture; multiple means ambiguous; one confidential record means identity withheld; one public record means matching ID. These are local reason codes, not a normative IAB status vocabulary.

The duplicate-ID fixture intentionally violates the one-entity-per-ID rule; its candidates are reported as ambiguous. Unrelated well-formed IDs in that same input remain usable for this diagnostic. By contrast any malformed required record invalidates the input and blocks all lookups. This distinction is not a conformance certification.

`is_confidential` follows the integer 0/1 representation in sellers.json 1.0 (July 2019), not a generic truthiness rule. JSON booleans/strings are uncheckable in this strict teaching parser; Google-specific prose referring to true/false is not used to silently change this schema.

The mixed ads fixture intentionally includes invalid rows. This tool inspects remaining rows for diagnostics; it does **not** decide that the overall ads file is usable for authorization. The ads.txt specification says obviously corrupted or malformed file contents should be ignored. Do not use diagnostic matches as a purchasing or authorization decision.

## Independent expectations

`fixtures/oracle.json` was hand-authored from the fixture scenarios before the checker. `verify.py` compares every data-row status/reason and all totals, checks ID preservation, differing domains, certification ID, duplicate provenance, confidential fields, independent relationship/type labels and stored variables. Five separate malformed-input regressions cover duplicate JSON members, NaN, an unrelated malformed record, a string confidentiality flag and an unsupported version.

The captured result is 16/16 fixture classifications plus 5/5 malformed-input regressions. There are 16 data rows: 2 invalid, 1 duplicate, 13 unique valid join candidates. Those 13 comprise 3 matching, 2 absent, 1 confidential, 1 ambiguous and 6 uncheckable. One mapped sellers input is unavailable (a deliberately missing local file). Two variable declarations are excluded from the data-row denominator. These counts describe fixture coverage, not real-world prevalence or success rates.

## Boundaries

No HTTP implementation, recursive crawling, redirects, freshness validation, app-ads.txt, subdomain/inventorypartnerdomain traversal, OWNERDOMAIN/MANAGERDOMAIN interpretation, extension fields or passthrough/SupplyChain validation. Unsupported rows can be classified invalid by this subset without implying the standard forbids them. No claims about fraud, legality, bids, ads served, users, conversions, spend or actual payment paths. ScrapingAnt is not needed for this local task.

## Source provenance

Inspected 2026-09-29. Full details, SHA-256 hashes and claim mappings are in `evidence.yaml`.

- [IAB ads.txt landing page](https://iabtechlab.com/ads-txt/) links the specification.
- [ads.txt v1.1, pinned revision 7682963](https://github.com/InteractiveAdvertisingBureau/Supply-Chain-Validation/blob/7682963ae241fe93a488f9508f28bcf9cdf50118/ads.txt%20v1.1.md), sections 3.3–3.5: account relationships, comments, records and variables. Source file includes the July 2022 1.1 release history.
- [Implementation Guidance at that same revision](https://github.com/InteractiveAdvertisingBureau/Supply-Chain-Validation/blob/7682963ae241fe93a488f9508f28bcf9cdf50118/Implementation%20Guidance.md), Case A: owner business domain can differ from inventory domain; further cases need transaction context.
- [IAB sellers.json landing page](https://iabtechlab.com/sellers-json/) links the [July 2019 sellers.json 1.0 specification](https://iabtechlab.com/wp-content/uploads/2019/07/Sellers.json_Final.pdf). Printed pages 6–9 define the parent, string seller IDs, unique identity, seller types, confidentiality and business domains.
- [OpenRTB SupplyChain specification, pinned revision f3fb64b](https://github.com/InteractiveAdvertisingBureau/openrtb/blob/f3fb64bb9e5fb0ae65bbf71feff6b7596e1e7d1a/supplychainobject.md), introduction: per-bid-request chain context.
- [Google Ad Manager seller information](https://support.google.com/admanager/answer/9761171?hl=en), business-domain and transparency sections. Its publisher IDs and product-specific handling are not generalized here.

Documentation research is separate from `run.sh`: the packet run makes zero network requests. Read-only specification retrieval was performed to inspect and hash official sources; no live ad-data target was fetched.
