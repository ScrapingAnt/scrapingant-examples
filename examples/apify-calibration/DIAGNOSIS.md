# Read-only diagnosis of the consumed attempt

The calibration execution guard is closed. One separately approved diagnostic dispatch can perform at most four GET requests using the existing Actions secret, never a start, retry, deletion, export, account mutation or privilege change. Default execution is offline:

```sh
python -m unittest test_diagnosis.py
python diagnosis.py
```

The fixed sequence is token-bound identity, the public Actor's run list (limit5, no pagination, UTC14:10:40–14:11:00 on2026-10-02), one candidate's full run metadata, then that run's default KV `INPUT` record. A complete empty list establishes only no matching run visible to this credential/window. Incomplete/ambiguous lists, HTTP/network errors, changed references, foreign ownership, build/options mismatches or inaccessible INPUT remain inconclusive. They never establish zero charge or authorize another start.

Exact correlation requires Actor identity, immutable build3.0.25, start time, same token/run owner,1024MB/120s/USD0.10 options, unchanged KV reference and exact typed JSON input. The optional `restartOnError` response field is checked if present; the official run response does not require that field. The published plan provides the expected input but stays unexecuted by this script.

Only fixed categories, HTTP status, request count and match booleans are retained. Identity, credentials, run/store IDs, private user fields and all raw responses remain ephemeral. Console/token comparison is explicitly null because this workflow has no private binding to the Console identity. Run/token ownership comparison occurs in memory. The diagnostic source gate is closed after this one dispatch.

Official endpoint semantics verified2026-10-02: [token identity](https://docs.apify.com/api/v2/users-me-get), [bounded Actor run list](https://docs.apify.com/api/v2/actors-runs-get), [exact run](https://docs.apify.com/api/v2/actor-run-get), [raw INPUT record](https://docs.apify.com/api/v2/key-value-store-record-get). No billing settings or financial history endpoint is used.
