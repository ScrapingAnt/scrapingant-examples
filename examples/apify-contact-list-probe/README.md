# One fixed Contact Actor-list diagnostic

This method makes at most one GET to the previously reviewed Actor-specific run
list. It keeps the original Actor, time window, ascending order, limit 5 and
offset 0. It stops after the response. It never starts, aborts or deletes an
Actor, exports items, follows redirects, retries, paginates or resumes another
test.

The guard is closed by default. Running `python -B list_probe.py` is offline.
`python -B -m unittest test_list_probe.py` uses named synthetic streams and
temporary files; those are not provider responses or customer invoices.
The public tests need neither an account nor a decryption identity.

## Native dispatch and source binding

The workflow first runs the offline tests on Python 3.10 and 3.12. Its provider
step requires explicit manual opt-in, `main`, attempt 1, the exact expected source
commit and an independently reviewed activation of this method's single guard.
Existing recovery and Actor-start guards remain closed. The workflow shares the
existing recovery concurrency group. The private operator must claim one durable,
exclusive dispatch intent before submission; uncertain submission is consumed
and must not be retried. Reclose the guard immediately after submission, then
authenticate native workflow/source/artifact metadata and decrypt privately.
An additional dispatch requires another reviewed intent and authorization.

The adapter checks the pinned scope and six existing dependency hashes again
before transport. It uses the existing Actions `APIFY_TOKEN` secret only in an
Authorization header. No new credential, identity or account setup is needed.
It preflights encryption before inspecting that token or opening the request.
The official age 1.3.2 executable is installed at the recorded archive digest;
the existing public recipient encrypts evidence. No private decryption identity
is available to the native workflow.

## Bounded response treatment

The transport change is explicit: the earlier diagnostic discarded HTTP error
bodies. This method reads **only HTTP 400 structured JSON errors**, at most
16,384 bytes, requiring bounded `error.type` and `error.message` strings. It
retains their exact response bytes encrypted as `list-error.age`. HTTP 200 list
responses have a 131,072-byte bound and use the unchanged page/candidate
validators. The request/read deadline is 15 seconds; capture has a 90-second
wall bound. Every other error body's content stays unread. Unexpected MIME,
compression, malformed JSON, credentials in a response, invalid list scope,
oversize data or expired deadlines stop without alternatives. Credentials are
rejected before persistence, including JSON-escaped values.

Only encrypted body, encrypted manifest and a fixed public projection are
uploaded, for seven days. The local intent and encryption preflight are excluded
from the artifact. Error type/message, response contents, candidate identifiers
and account meters never appear in the public projection. Independent private
readback must bind exact activated source, native run/jobs/artifact metadata,
archive digest, member allowlist, decrypted byte commitments and response
semantics. Incomplete or unverified capture remains an explicit stop.

An empty page proves only absence in the bounded window. A unique candidate
proves only a list observation. Neither completes terminal identity, INPUT,
meter or accepted-output verification. Every outcome retains the full Contact
hold, unknown charge/output values and a closed gate for any next Actor start.

## Source interpretation

[Apify's official Actor-list documentation](https://docs.apify.com/api/v2/actors-runs-get)
was checked on 6 October 2026. It documents the route and supplied filters; it
does not establish the cause of a particular HTTP 400. The original UTC bounds
are preserved exactly. The published millisecond examples do not establish a
three-digit fractional precision limit. No actual server acceptance or provider
root cause is inferred from those examples.
