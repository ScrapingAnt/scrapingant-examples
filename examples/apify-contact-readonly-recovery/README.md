# Prospective Contact start diagnostic

This is a closed method for one earlier bounded Contact pilot start request.
It is not a new Actor run or a retry. Named synthetic tests use fake responses;
no actual account observations or results are included here.

The fixed list request selects public Actor `vdrmota/contact-info-scraper`, pinned
build `0.2.238`, within the original UTC minute, limit five, offset zero, ascending.
All returned times and Actor IDs must match. A complete unique page may select
one candidate; incomplete or multiple-candidate pages stop without pagination.
The existing owner's SHA256 commitment is part of the separately approved scope.
No raw protected owner, run or store identifier is committed and no new credential
or protected identifier configuration is required. Publishing the derived owner
commitment is included in the publication approval boundary.

Maximum ordered GETs:

1. The fixed Actor-specific run-list page.
2. The unique candidate's exact run, requiring owner, build, USD0.50 cap,
   memory512 MiB, timeout120 seconds, start window and native default stores.
3. Its default KV metadata, requiring exact owner/Actor/run association, explicit
   `name:null` and creation inside the run/observation window.
4. That verified KV's `INPUT` record, whose canonical native input must match the
   original six synthetic contact pages and all original options exactly.
5. The same terminal run's final meter, with identical identity/status/timestamps.
   The latest header is used once. Initial/detail components are never added to it.

Each response is at most131072 bytes and15 seconds; the transport has90 seconds
of cumulative wall time including encryption between requests. Authentication is
header-only. Redirects, retries, pagination, starts, aborts, output item exports,
deletion, settings changes and account enumeration are unavailable. Native bodies
and manifest are age-encrypted with the existing public recipient; error bodies
are not read or retained. A synthetic encryption preflight precedes token access.

A complete empty filtered list establishes only an observed absence in that
response. It does not establish that the HTTP400 request was rejected before run
creation, imply zero charges, recover a meter, or automatically authorize any
start. A nonterminal, malformed, truncated, mismatched or ambiguous observation
stops. Recovery always emits `ready_for_next_Actor_start:false` and releases no hold.
The original Contact attempt stays consumed with its fullUSD0.50+0.03 reservation.
The private combined decision specifies the separate conservative resumption gate.

Offline validation: `python -B -m unittest test_recover_contact.py`.
The workflow's manual opt-in defaults false, main and attempt one are mandatory,
and source activation must be reversed immediately after dispatch. No external
action is authorized merely by this README or by passing tests.

Endpoint semantics were reused from the project's previously verified official
[Actor run list](https://docs.apify.com/api/v2/actors-runs-get),
[Get run](https://docs.apify.com/api/v2/actor-run-get),
[KV metadata](https://docs.apify.com/api/v2/key-value-store-get), and
[KV record](https://docs.apify.com/api/v2/key-value-store-record-get) contracts.
No fresh provider or public web reads were made while preparing this candidate.
