# Measured Requests cookie behavior

Measured September 27, 2026 on macOS 26.6.2 arm64, Python 3.12.10, Requests 2.34.2 and urllib3 2.8.0. Complete versions are in the JSON captures and dependency lock. The local command is `./run.sh` after installing that lock.

The final execution passed all 24 boundary/integration tests and all 54 matrix checks. The matrix comprises 12 extraction cases × 3 rounds (36 observations) and 6 diagnostics × 3 rounds (18 observations). Every extraction returned HTTP 200 and exactly four rows. Only four states matched the independent literal member/EUR oracle: 12 exact extractions, or 48 matching tuples out of 144 expected tuple comparisons across deliberately mixed positive and negative controls. Those totals are not a production success rate.

| Case | State observed in catalog | Correct records per round |
|---|---|---:|
| Independent short-lived Sessions | Retail/USD; earlier session closed | 0/4 |
| Persistent Session | Member/EUR | 4/4 |
| `cookies=source_jar` for one call | Member/EUR; receiving Session still stores zero cookies | 4/4 |
| Next call without `cookies=` | Retail/USD | 0/4 |
| Final `response.cookies` only | Retail/EUR; earlier redirect's session missing | 0/4 |
| Full LWP restore | Member/EUR; three scoped entries retained | 4/4 |
| `get_dict()` dictionary roundtrip | Member/USD at the EUR URL; three entries collapsed to two | 0/4 |
| `Request.prepare()` | Retail/USD despite seeded Session | 0/4 |
| `Session.prepare_request()` | Member/EUR | 4/4 |
| Session cookie given past expiry | Retail/EUR; session cookie absent on wire | 0/4 |
| Explicit domain/path/name clear of session | Retail/EUR; session cookie absent on wire | 0/4 |
| Simulated server-side revocation | Retail/EUR; session cookie still present on wire | 0/4 |

Each row above has three observations with identical results. Prices are integer minor units, not binary floating-point currency amounts.

## Diagnostics

The redirect response held one cookie. The final response held two region cookies. The Session held all three. This is why persisting only the last `response.cookies` misses the session in this particular response chain; it is not a claim that a response jar can never contain authentication cookies.

The same jar selected member/USD records at `/catalog/us/products` while sending exactly one region cookie, and member/EUR at `/catalog/eu/products`. `get_dict()` lost the path distinction and selected USD at the EUR URL. The output stores the four resulting records and server-derived `region_is_eur`/`region_is_usd` booleans, not Cookie-header text.

Name-only region lookup raised `CookieConflictError` in all three rounds. An explicit domain/path lookup selected the intended region. Clearing that exact tuple retained the other region cookie.

Both unsupported direct keywords (`httponly`, `samesite`) raised `TypeError` in all rounds. These are constructor API diagnostics; they say nothing about browser enforcement. Mounting an HTTPS adapter left the HTTP adapter present and the HTTP fixture request returned 200 in every round.

## Persistence and scoring boundaries

Tests check session-cookie opt-in separately on save and load; exclusion of expired entries at both steps; distinct region paths on prepared requests; preserved Secure/HttpOnly/SameSite metadata; omission of a Secure cookie from a prepared HTTP request; private file mode; refusal to overwrite an existing file or symlink; and refusal to load a group-readable snapshot. The chosen LWP representation is plaintext. No real authentication state is stored or printed.

The initial membership-based oracle failed two regression tests: four duplicates scored four instead of one, and five rows including a duplicate scored five instead of four. The captured failure output is preserved with source-path prefixes normalized. Counter intersection and exact multiset equality fix both. All final tests and primary captures use the corrected oracle. Additional summary tests reject missing/duplicated cases and scores inconsistent with captured records.

## Scope

The servers bind loopback only, and all clients ignore ambient proxy and `.netrc` settings. The local sandbox initially blocked loopback binding; the same tests passed when run with loopback permission. No external endpoint, secret or paid call was used.

The independent-requests control uses one short-lived Session per request; it does not directly exercise the top-level `requests.get()` convenience function. The expiry check assigns a past timestamp instead of waiting. Revocation is simulated by fixture state. The fixture has no JavaScript, browser storage, cross-site request or TLS handshake. LWP roundtrip and file mode were measured on macOS; production session reuse, OS-independent permissions and browser-security equivalence are not claimed.

`verification.json` binds executable source and captures by SHA-256 and records the completed independent automated review and Linux CI. The committed primary captures remain the macOS observations described above.

## Publication verification

Executable source: `daa3b8bfe914b160e622be41fbf05ef161f4f2c6`. [Linux CI passed](https://github.com/ScrapingAnt/scrapingant-examples/actions/runs/36334992162) before the evidence pull request was opened: 24 tests and 54/54 designed matrix checks. See [verification.json](verification.json) for hashes and the exact CI source. No executable code or primary captures changed when this provenance was recorded.
