# Bounded owned-fixture smoke

This directory implements one manual, source-reviewed Cheerio smoke against
three owned synthetic static pages. Fixtures are ground truth; they are not
Actor results. The committed default is offline and all live guards are closed.
Other candidate cells are present for later review but the workflow accepts only
`smoke-cheerio-scraper`.

The first cell uses build3.0.22, query memory4096MB, concurrency1, a120s run
timeout, aUSD0.12 total run cap and a separateUSD0.02 ancillary reservation.
Its hook disables request retries, session-error retry paths and redirects,
then waits200ms before each of exactly three owned document requests. Cheerio
does not execute scripts or fetch page subresources. These smoke inputs do not
provide a runtime benchmark or an estimate of arbitrary-site success.

The two phases are deliberately separate:

1. Capture verifies the original run, exports at most four rows (three assigned
   rows plus an extra-row sentinel), and checks the three original unnamed
   default-store associations. Only allowlisted numeric meters and controlled
   outputs enter the private receipt. The standard age1.3.2 CLI encrypts it to a
   public recipient; raw scope identifiers stay in memory or a0600 runner-temp
   state file. No plaintext receipt/state or private identity key is uploaded.
2. The owner-side process downloads the ciphertext, authenticates/decrypts it
   locally, validates its scope, fsyncs the plaintext file and directory and
   checks exact readback. Only after that proof does it commit a hash-only
   approval to the existing repository's main branch. Without the matching
   plaintext/ciphertext hashes and scope approval, cleanup performs no provider
   GET or DELETE. A fresh terminal run and fresh unnamed/owner/run/store metadata
   must still pass before deleting only those newly created defaults. Each
   deletion requires204 followed by a typed404 absence check.

Approval waits stop within25minutes of run completion. Cleanup has a separate
120s wall bound and each deletion must occur within30minutes of completion.
At most20 provider requests are permitted, including original capture requests
and cleanup. A same-original-run active status revokes all remaining requests,
even if other response fields are malformed. A failed capture, named resource,
unverified association, lost key, missing approval or expired deadline retains
resources and reports that owner attention is required. It never infers zero
cost from missing data and never retries a failed start automatically.

Public artifacts/logs contain ciphertext, safe fixed diagnostics, counts and
hashes. Run/account/store identifiers, charges, extracted text and private
repository paths are excluded. The final encrypted receipt preserves refreshed
preliminary run meters, storage quantities and cleanup confirmations. Neither
API run meters nor this smoke establish a final invoice.

Run offline tests with the official age binaries available:

```sh
STUDY_TEST_AGE_BIN=/absolute/path/to/age python -m unittest discover -p 'test_*.py'
python workflow_driver.py capture
```

Official parameter and resource references, checked2026-10-02:

- [Run Actor](https://docs.apify.com/api/v2/actors-runs-post): query `memory` is in
  MB; `maxTotalChargeUsd` caps all pricing models; build/timeout/restart overrides.
- [Actor resources](https://docs.apify.com/actors/running/usage-and-resources):
  power-of-two memory allocations,4096MB per CPU core.
- [Standard age tooling](https://github.com/FiloSottile/age/releases/tag/v1.3.2):
  reviewed official binaries, release digests verified before use.
- [Pinned Cheerio source](https://github.com/apify/actor-scraper/tree/236f190d6c3dc7ab660f97c9291382b77e204aae):
  deployed build/schema pin and raw HTTP extraction behavior.
