# Python Requests cookies: sessions, scope and reliable extraction

Runnable evidence for [Python Requests cookies](https://scrapingant.com/blog/manage-cookies-python-requests). The catalog, session and prices are synthetic. No account, API key, paid service, browser or external target is involved.

## Reproduce

Use Python 3.12 on macOS or Linux. The capture uses Python 3.12.10 and Requests 2.34.2; it does not claim these are the newest releases.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python quickstart.py
./run.sh
```

Installation needs a package index or cached wheels. Execution uses temporary `127.0.0.1` HTTP servers only, with proxy and `.netrc` processing disabled. It needs permission to bind a loopback port. `run.sh` executes all 24 tests, the complete quickstart, and three matrix rounds. It writes ignored `run_output/`; it never overwrites committed `expected_output/`. `PYTHON_BIN` can select a Python interpreter. No environment variable enables an external or paid request.

The complete `quickstart.py` obtains cookies through a redirect, writes a new private LWP file, closes the first Session, restores the jar into a fresh Session and validates four extracted records. The final redirect response contains two cookies; the accumulated Session has three. The temporary snapshot and fixture are cleaned up on exit. Output contains product records, cookie counts and derived booleans, not cookie values or headers.

## The extraction check

The fixture has independent member/retail and EUR/USD price schedules. Every catalog response deliberately returns HTTP 200 and four rows. `oracle.py` imports no fixture data: it specifies these expected tuples literally and compares multisets using `Counter`:

| SKU | Currency | Price in minor units |
|---|---|---:|
| BK-101 | EUR | 1499 |
| PN-202 | EUR | 799 |
| NB-303 | EUR | 2199 |
| BG-404 | EUR | 4299 |

A duplicated correct row cannot stand in for a missing SKU. `expected_output/oracle-regression-red.txt` preserves the actual initial failing regression output, with only local source-directory prefixes normalized. Four copies of the first row initially scored four matches; the corrected oracle scores one. An extra duplicate also prevents an exact match.

There are 12 extraction cases and six diagnostics per round: 36 extraction observations and 18 diagnostic observations across three rounds, with four expected records per extraction. Four cases match all four records; the eight intentional failure/control states match none. Passing all 54 checks means the controls behaved as specified, not a 100% production extraction rate.

See `report.md` for the case table. The central scope comparison has two cookies called `region` on distinct paths. Full restoration sends the EUR cookie to the EUR catalog and the USD cookie to the US catalog. `get_dict()` collapses them: in this fixture's insertion order the USD value survives, and a dictionary roundtrip actually selects member/USD records at the EUR catalog URL. The server records boolean observations from the received Cookie header; no raw header is published. The survivor of flattening is not a universal rule.

## Persistence policy

`cookie_state.py` uses standard-library `LWPCookieJar`, retaining the scoped entries and supported metadata. `save_private_jar()` creates a new file with POSIX mode `0600` and refuses existing paths, including symlinks. It does not print the jar. `load_jar()` requires a regular file and refuses group/other permissions on POSIX. The quickstart uses a temporary private directory. These narrow safeguards do not make the plaintext format encrypted or suitable for publication.

Session/discard cookies are excluded by default. This demo explicitly passes `include_session=True` on **both save and load** because restoring the synthetic session is the task. Expired cookies are excluded on both operations even with that opt-in. The expiry matrix case separately gives the session cookie a past expiry and measures that Requests omits it from the actual request; it does not wait for natural expiration. A real server can still revoke otherwise unexpired state.

The HTTP fixture is deliberately local. Its synthetic session cookie is HttpOnly but not Secure so Requests can transmit it over local HTTP. A separate offline boundary test shows a Secure cookie is omitted from a prepared HTTP request and metadata can survive LWP persistence. This is not a TLS test or a browser SameSite/JavaScript policy test. `HttpOnly`/`SameSite` metadata in `http.cookiejar` does not establish browser enforcement by Requests.

## Cookie operations and limits

- Independent request control uses two short-lived `Session` objects, one per request; the first closes before the catalog request. This explicitly isolates state while preventing ambient proxies or credentials. The top-level `requests.get()` convenience wrapper is not directly measured here.
- `cookies=jar` supplies the next request without storing those supplied entries in the Session; server responses could still set new persistent entries. This fixture's catalog responses set none.
- `response.cookies` contains the final response's received cookies. `response.history[0].cookies` shows the redirect's earlier session cookie; `session.cookies` accumulates both responses.
- With duplicate names, `jar.get('region')` raises `CookieConflictError`. Use `jar.get('region', domain='127.0.0.1', path='/catalog/eu')`; use the same domain/path/name tuple for `jar.clear()` when removing one scoped entry.
- `Request.prepare()` omits Session state. `session.prepare_request()` applies it. The local demo disables environment settings; production callers using prepared requests must separately consider documented environment merging.
- Passing `httponly=` or `samesite=` directly to `RequestsCookieJar.set()` raises `TypeError` in the measured version. Optional metadata belongs in a Cookie's `rest` mapping; this is not a browser security guarantee.
- Mounting an adapter on `https://` leaves the existing `http://` adapter available. The diagnostic actually completes an HTTP fixture request; it does not implement an HTTPS-only policy.

The evidence does not cover production authentication, session renewal, browser state portability, anti-blocking, cross-site SameSite, SSO, MFA or IP-bound sessions. Three repeats of a deterministic fixture do not estimate production reliability. Cookie file permissions are tested on macOS; Windows permission semantics are not claimed.

## Files and primary references

`catalog_fixture.py`, `requests_matrix.py` and `quickstart.py` are executable source. `test_*.py` and `run_checks.py` cover persistence, oracle, actual wire behavior and incomplete-summary rejection. `requirements-lock.txt` pins Requests and its complete runtime dependency set. `comparison.json` is derived from the committed capture:

```bash
python summarize.py > run_output/rebuilt-comparison.json
```

Primary references checked September 27, 2026: [Requests sessions and prepared requests](https://requests.readthedocs.io/en/latest/user/advanced/), [Requests cookie API](https://requests.readthedocs.io/en/latest/api/#api-cookies), [Requests cookie implementation](https://requests.readthedocs.io/en/latest/_modules/requests/cookies/), and [Python http.cookiejar](https://docs.python.org/3/library/http.cookiejar.html).

This packet makes no ScrapingAnt calls. Any article discussion of receive/replay through ScrapingAnt must cite the separately captured experiment in `examples/selenium-set-cookies/expected_output/scrapingant.json`, not imply this local catalog was sent through that service.
