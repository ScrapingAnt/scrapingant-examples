# Test a scraper's failure contract

Local evidence for `/blog/production-ready-scrapers-in-2025-what-broke-what-works-now`.
All data is synthetic, served on 127.0.0.1. No credentials, scraping API, external
website, browser, paid service or model is called.

## Run

Tested with Python 3.12.11. Create a virtual environment and install the complete
pinned dependency list:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

`run.sh` overwrites captured outputs and exits nonzero if policy tests or the
observed matrix differ from independently specified expectations. A sandbox must
permit a loopback TCP listener. `PYTHON=/path/to/python ./run.sh` chooses an
existing prepared environment. Dependencies are HTTPX and jsonschema plus their
pinned transitive dependencies; the fixture, storage and runner use the standard
library. No dependency installation occurs inside `run.sh`.

## What is being proved

The direct-GET client has at most three total attempts, a 1-second HTTPX IO
timeout, and a separate 6-second asyncio deadline shared across attempts and
backoff. These are deliberately tiny laboratory settings, not production
recommendations. A valid Retry-After is never shortened; if its wait cannot fit,
the job returns `retry_deferred`. Only declared transient HTTP statuses and
network/timeout errors enter the retry path. Bad content, schema errors, a failed
USD business rule and a failed sink write are terminal. The response-body cap is
65536 bytes. Redirects and environment proxies are disabled in this local runner.

JSON Schema describes the fixture record; a USD-only business rule is separate.
The scraper never reads `fixtures/oracle.json`. The independent evaluator compares
stored values with that oracle. `wrong_price` deliberately passes both schema and
currency checks and is stored, exposing a factual validation gap. Expected
behavior checks passing do **not** mean every stored record is correct.

SQLite uses a primary key in an isolated in-memory database per scenario.
Replaying the same successful record leaves one row. A query-only SQLite
connection causes an actual write failure. This is a small delivery demonstration,
not durable restart recovery, changed-record conflict resolution or distributed
exactly-once delivery. Keep invalid jobs' events and body previews for diagnosis;
this packet has no automatic replay queue or external quarantine store.

## Files

- `scraper.py`: acquisition, extraction, JSON Schema/business checks and delivery.
- `fixture_server.py`: deterministic HTTP response sequences and real slow bodies.
- `fixtures/catalog.html`: authored input with an embedded record script.
- `fixtures/record.schema.json`: Draft 2020-12 record contract.
- `fixtures/expected_cases.json`: independent expected outcome/attempt/row manifest.
- `fixtures/oracle.json`: evaluator-only known correct record.
- `test_policy.py`: focused Retry-After parsing tests.
- `run_matrix.py`: real HTTP matrix and independent sink/outcome assertions.
- `expected_output/naive_control.json`: six pages return 200, including invalid data.
- `expected_output/events.jsonl`: phase events, attempts, retry waits, terminal
  outcomes and bounded synthetic body previews; no credentials.
- `expected_output/fixture_requests.json`: target-side counts/timestamps.
- `expected_output/stored_records.json`: snapshots of each isolated SQLite sink.
- `expected_output/report.json`: summary, per-case assertions and per-job durations.
- `expected_output/run.txt`, `policy_tests.txt`: actual command output.
- `evidence.yaml`: measured claims, environment, denominators and limitations.

## Scope and limitations

Nineteen scenarios run three times. The duplicate scenario starts two jobs, so
57 scenario checks correspond to 60 jobs, not 57. Matrix HTTP-attempt totals
exclude the six separate naive-control requests. Each repetition uses fresh
fixture counters and each scenario a fresh sink; no production success-rate
inference is valid. Schema pass counts exclude pages that failed extraction.
Oracle precision is over stored records across isolated scenarios, not globally
deduplicated entities. Repeated records across independent tests remain separate
observations.

The trickle response sends a byte every 0.05 seconds, below the 1-second read
inactivity threshold; the absolute deadline interrupts it. Deadline assertions
allow 1 second of scheduling tolerance. Async cancellation is cooperative:
this does not prove interruption of arbitrary blocking parsing/database code or
that a remote service stops work when a client gives up. Fixtures are tiny and
SQLite lock waits are disabled. No browser readiness, actual CAPTCHA detection,
TLS/DNS/connect-timeout fault, high concurrency or remote sink was tested. The
body cap is implemented, but the network matrix does not contain an oversized-body
case. Invalid/missing Retry-After falls back to the configured bounded backoff;
HTTP-date handling is unit-tested, not a separate live HTTP scenario.

A development rerun with a 0.15-second IO timeout hit an unintended read timeout
on the trickle fixture; its 56/57 result and relevant events are retained in
`expected_output/development_failure.json`. An intermediate setup widened IO inactivity
to 0.5 seconds and total budget to 2.5 seconds; expected attempt counts remained
unchanged. Final captured measurements refer only to the final configuration below.

A later loaded-host run at 0.5-second IO/2.5-second total timing produced
55/57 expected checks: two stalled-body jobs reached the overall deadline
instead of exhausting three read timeouts, and one finished at 2.820 seconds.
Those events are retained in `expected_output/development_scheduling_failure.json`.
The final lab settings are IO 1 second / total 6 seconds, with an explicit 1 second
scheduling allowance, preserving the expected outcome assertions. This illustrates
why these are cooperative cancellation budgets, not hard real-time guarantees.
