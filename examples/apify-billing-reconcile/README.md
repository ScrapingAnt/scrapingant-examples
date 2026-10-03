# Fixed read-only monthly billing diagnostic

Closed by default. Exactly two GET attempts: October 3, 2026 monthly usage and current limits. No Actor starts, deletion, profile, payment, storage, token-management or proxy routes. Authentication uses only the existing workflow secret in the Authorization header; no local credential, account creation or paid tool.

Failures consume an attempt and stop; no retries or redirects. Each response is at most 128 KiB, each route 10 seconds and total route budget 30 seconds. Strict Decimal JSON parsing and a fixed allowlist project authoritative reported totals without summing service/day values, subtracting an allowance or attributing account residuals to this study. Cycle comparability is explicit.

Financial projections remain authenticated-encrypted with the existing age recipient. Only fixed read categories, booleans and hashes are public. Raw API responses and exact account financial values are not published. The original 1 MiB encryption helper is unchanged. No run settlement or invoice attribution is inferred.

Offline: `python -B -m unittest discover -p 'test_*.py'` (21 deterministic tests). `python billing_readonly.py` uses no provider. `--execute` is blocked until the separately reviewed source guard is activated.

Official sources, checked October 3, 2026: https://docs.apify.com/api/v2/users-me-usage-monthly-get and https://docs.apify.com/api/v2/users-me-limits-get and https://docs.apify.com/account/billing .
