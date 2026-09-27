# Cookie state can change the dataset without changing the row count

Tested 2026-09-27. Selenium 4.49.0; Python 3.12.10; macOS 26.6.2 arm64. Primary browsers: Chrome 154.0.8037.57/ChromeDriver154.0.8037.57 and Firefox 156.0.1/geckodriver0.37.1. Each ran three rounds of 13 cases: 78 assertions passed. Sixteen offline tests also passed. A separate quickstart execution restored two cookies and extracted all four intended records.

## Primary extraction results

| Case | HTTP status | Rows returned | Correct member-EUR records | Observations |
|---|---|---|---|---|
| Anonymous |200|4|0/4|6|
| Server-seeded session and region |200|4|4/4|6|
| Full snapshot restored in a fresh browser |200|4|4/4|6|
| Session cookie only |200|4|0/4|6|
| JavaScript-visible cookies only |200|4|0/4|6|
| Session cookie on the wrong path |200|4|0/4|6|
| Expired session filtered before restoration |200|4|0/4|6|
| Session revoked on the server |200|4|0/4|6|
| Session cookie deleted |200|4|0/4|6|

These 54 observations agree in both primary browsers and all three repetitions. The oracle is the exact SKU/currency/price tuple for each of four independently listed products, not the fixture's own price-generation function. Member-EUR prices are 800/1600/2400/3200 minor units; no live currency conversion or production pricing is involved.

The session-only case still selected member pricing, but in USD: row-count and login-state checks would both miss the wrong currency. JavaScript-visible-only restoration retained the EUR preference but omitted the HttpOnly session, selecting retail prices instead. Revocation left the cookie in the browser while the fixture rejected its session. A present cookie is not proof of current authentication.

In all six primary diagnostic observations per case, cookie insertion on about:blank and an unrelated domain raised `InvalidCookieDomainException`. WebDriver could see the HttpOnly demo session while document.cookie could not. Delete-all left no cookies associated with the current fixture document. The separate installed-Firefox 109.0.1 exploration also passed but is not blended into the primary count.

## ScrapingAnt cookie round trip

Eight calls, four per mode, one observed chain per mode. The key was provided in a header and was not written to a capture. Two synthetic cookie names were allowlisted; arbitrary response data was discarded.

| Mode | Baseline | Receive after set | Separate request without replay | Explicit replay | Measured credits |
|---|---|---|---|---|---|
| browser=false, datacenter | No demo cookies | Both pairs received and echoed | No demo cookies | Both values echoed by target |4|
| browser=true, datacenter | No demo cookies | Both pairs received and echoed | No demo cookies | Both values echoed by target |40|

All API and target statuses were 200. All eight credit receipts were present, totaling 44. The returned `cookies` field contained the expected pairs; the response body field was `html`. A new call without explicitly replaying the received values returned no demo cookies. This supports explicit receive/send chaining on this endpoint; it does not establish cross-site login portability, universal session persistence or effectiveness on a protected production website.

## Interpretation

Use cookie state as an input to the extraction contract: expected session role, currency/region and exact record fields. Treat a successful navigation, cookie presence and row count as separate checks. Restore only a narrowly scoped snapshot on its intended origin; verify the data again after restoration or a session renewal.

The local HTTPS fixture intentionally makes failure visible and deterministic. It provides examples of failure mechanisms, not prevalence estimates, performance comparisons or production success percentages. Repeats share a machine and fixture implementation. No cross-site SameSite or partitioned-cookie experiment was performed. ScrapingAnt's public echo test is separate from the localhost catalog, which its remote infrastructure cannot reach.

The original pre-oracle-fix Chrome/Firefox captures are preserved under `expected_output/exploratory/`. The final primary captures were rerun after fixing duplicate-row matching; the results are unchanged.
