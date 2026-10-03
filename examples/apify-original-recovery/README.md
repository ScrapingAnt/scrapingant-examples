# Exact original evidence recovery

This closed diagnostic retrieves the original completed synthetic Playwright
dataset and existing log using the already configured APIFY_TOKEN. It creates
no new Actor, retries, store mutations, account changes or credentials.

Seven ordered GETs maximum: one five-row Actor run-list page within a fixed UTC
minute, the hash-selected original run, its freshly verified unnamed dataset,
raw JSON with hidden/empty fields retained, clean JSON, the original eleven-field
clean projection, and the existing run log. No alternate target, pagination,
redirect, replay or automatic retry is supported. Full original identity/build/
options/status commitment must match before store or log access. Denied
authenticated access stops immediately; it is not replaced with anonymous reads.

Each raw body is age-encrypted separately, preserving exact bytes, hashes,
headers and row counts in an encrypted manifest. Public output contains only
fixed status/count/diagnostic fields and hashes. Native owner/run/store IDs,
raw records/logs and all measured study results remain private. Unselected list
records are not retained. The owner's age identity remains local.

Metadata responses are capped at128KiB; exports/log at8MiB each; each GET has a
15-second cumulative route limit and transport has a120-second shared deadline.
Encryption and durable readback are checked before token lookup. Existing outputs
or dangling output links block execution. The original paid-run guards stay closed.

Run `python -B -m unittest test_recover_original.py` offline. Without `--execute`
the helper makes no requests. Live execution additionally requires the separately
reviewed source guard, explicit manual opt-in, main, attempt one and passing
secret-free tests on Python3.10/3.12. After one dispatch the source guard is closed.
This operation does not approve cleanup or release any study reservation.

Endpoint semantics: [Actor runs](https://docs.apify.com/api/v2/actors-runs-get),
[dataset items](https://docs.apify.com/api/v2/dataset-items-get), and
[run log](https://docs.apify.com/api/v2/actor-run-log-get).
