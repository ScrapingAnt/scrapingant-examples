# Selenium cookies: extracted data versus a successful page load

Runnable evidence for [Selenium cookies](https://scrapingant.com/blog/selenium-set-cookies). All catalog records, accounts and cookie values are synthetic. No real login is performed.

## Install and reproduce

Use Python 3.12, Chrome, and `openssl`. Selenium Manager resolves a matching driver and may download it. Firefox is needed only for the optional second-browser run. Measured versions are recorded in the captures; an installed browser can differ from those versions.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python quickstart.py
./run.sh
```

`quickstart.py` starts a local HTTPS fixture, obtains its synthetic session, sets the region cookie, saves a JSON snapshot and restores it in a fresh Chrome process. The four expected products have EUR member prices in integer minor units. The snapshot is temporary and removed on exit. The helper can write to a caller-chosen private location; do not put real snapshots in Git or logs.

`./run.sh` executes 16 offline tests and three Chrome rounds (39 browser assertions). It does not call ScrapingAnt, even if `SCRAPINGANT_API_KEY` exists. Rerun output goes to ignored `run_output/`; committed `expected_output/` is never overwritten by these commands.

To repeat both browser suites:

```bash
./run.sh --all-browsers
```

The default uses installed browsers. To request the Firefox version measured here through Selenium Manager:

```bash
FIREFOX_VERSION=156.0.1 python browser_matrix.py --browser firefox --rounds 3 --output run_output/firefox-156.json
```

`CHROME_BINARY` and `FIREFOX_BINARY` optionally select known binaries. `SE_CACHE_PATH` can select a writable driver/browser cache. Browser downloads require network access; the actual catalog tests use localhost only. The fixture generates a temporary self-signed certificate, and these local test drivers accept it. Do not carry that certificate exception into real scraping code. The examples were measured on macOS; default Chrome checks also have a Linux CI entry. Windows is not claimed tested.

## What is measured

The fixture has independent member/retail and EUR/USD price schedules for four SKUs. Every catalog response intentionally returns 200 and four rows. `browser_matrix.py` uses a separate literal four-record oracle and checks the SKU, currency and price together.

Nine extraction cases per round: anonymous, server-seeded, full restore in a fresh browser, session cookie only, JavaScript-visible cookies only, wrong session path, expired session filtered out, server-side revocation and deletion of the session cookie. Four additional diagnostics check about:blank insertion, wrong-domain insertion, HttpOnly visibility and delete-all behavior.

The primary comparison has three rounds in Chrome 154.0.8037.57 and three in Firefox 156.0.1: 78 browser assertions and 54 extraction observations. Each case therefore has six observations; each observation has four expected records. Repeated deterministic fixture checks do not estimate production success rates. An earlier run with installed Firefox 109.0.1 is retained under `expected_output/exploratory/` and excluded from the primary comparison.

Rebuild the result summary without any browser, key or network request:

```bash
python summarize.py > run_output/rebuilt-comparison.json
```

## Sending and receiving cookies with ScrapingAnt

This separate probe uses the fixed public `httpbingo.org` cookie echo endpoints and two synthetic cookie values. It is a cookie-transport test, not an authenticated catalog scrape or a login-portability guarantee.

Inspect the non-live plan:

```bash
python scrapingant_cookies.py
```

Supply `SCRAPINGANT_API_KEY` through the environment or a secret manager. Never paste it into source, a saved command, a URL or an output file. Explicit live execution:

```bash
./run.sh --scrapingant
```

This permits at most eight API attempts: baseline, receive-after-set, independent no-replay request, explicit replay; first without a browser, then with a browser. Missing receive results skip that mode's replay. No automatic retries. An existing output file blocks a second run; choose a fresh `OUTPUT_DIR` only when deliberately authorizing a new paid experiment. The captured run used 44 credits: four 1-credit non-browser calls plus four 10-credit browser calls. Future costs and behavior can change; the runner records receipts and missing receipts separately.

Authentication is sent only in the `x-api-key` header to the fixed API host; API redirects are disabled. Output is allowlisted: statuses, credits, expected-cookie names and boolean comparisons. It does not contain the key, complete cookie strings, raw bodies, arbitrary headers or raw error messages. Returned cookie pairs are filtered to the two known synthetic values before replay to the same fixed target. Routine CI never runs this probe.

The measured response body field is `html`; the extended `cookies` field supplies the received pairs. The explicit replay passes those values with the `cookies` parameter using the HTTP client's encoding. The original WebDriver metadata (domain, path, HttpOnly, Secure, expiry and SameSite) is not represented by that string. Do not flatten a multi-site browser cookie jar and send it wholesale.

## Files and limits

- `catalog_fixture.py`: synthetic HTTPS origin, issued session, region-dependent records and simulated server revocation.
- `cookie_state.py`: exact-origin JSON helper, expiry filtering, preserved supported attributes and owner-only POSIX file permissions. It deliberately refuses parent/foreign cookie domains and omits Domain on restore to limit scope to the exact current host. It is not a general browser-profile exporter; snapshots include only cookies associated with the current document, and omit storage/partition metadata not exposed by classic WebDriver.
- `browser_matrix.py`, `quickstart.py`: browser evidence and minimal reader path.
- `scrapingant_cookies.py`: opt-in bounded product probe.
- `test_cookie_state.py`, `test_scrapingant_cookies.py`: offline boundary and spending/privacy checks.
- `comparison.json`, `report.md`, `evidence.yaml`: derived results, interpretation and provenance.

Expired-cookie filtering is an application-side decision before `add_cookie`; it does not test waiting for natural browser expiration. Server revocation is explicitly simulated by the fixture. SameSite cross-site navigation, partitioned cookies, browser profiles, local/session storage, MFA, SSO, IP-bound sessions and real accounts are outside the experiment. JSON is not encryption; file permissions do not make a cookie jar suitable for publication.

The original pre-oracle-fix Chrome/Firefox captures are preserved under `expected_output/exploratory/`. The final primary captures were rerun after fixing duplicate-row matching; the results are unchanged.
