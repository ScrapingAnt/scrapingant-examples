# Error 1005: offline response acceptance gate

This packet uses six owned, synthetic response snapshots. It makes no HTTP requests, reads no API keys and changes no access controls. The HTML marked Error 1005 is authored fixture text, not a captured Cloudflare response. A denial body with status 200 intentionally tests a downstream response-wrapper failure; it is not a claim about Cloudflare's normal status code.

Prerequisite: Python 3.10 or later, standard library only. Tested locally with Python 3.10.2. No package installation needed.

```bash
git clone https://github.com/ScrapingAnt/scrapingant-examples.git
cd scrapingant-examples/examples/cloudflare-banned-solution
./run.sh
```

For a pinned reproduction use the executable-packet commit in `evidence.yaml` before changing directories.

```bash
python3 diagnose.py fixtures/denied-200.json
```

This prints diagnostics and exits 2 (`stop`), without a `records` value. Accepting the valid snapshot exits 0. The example expects a non-empty JSON catalog with unique non-empty string IDs, non-empty string names and finite, nonnegative decimal-string prices. It rejects any unexpected envelope/record keys. Adapt the schema to your actual permitted endpoint; this is not a universal HTML parser or block detector.

## Limits and operational use

- No real Cloudflare target, browser, ASN/IP policy, CAPTCHA, ScrapingAnt API or billing behavior was tested.
- `possible_1005_page` is a conservative label for HTML containing `Error 1005`, not proof of response origin. Status/MIME alone do not authenticate a response or guarantee correct records.
- The CLI has no retry, alternate egress, proxy rotation, cookie clearing, header spoofing or publishing sink. It stops and lets an operator investigate.
- A production fetcher needs its own deadlines, size limits, trusted transport and capture storage. Do not log secrets/cookies or entire private bodies. A production schema needs independent correctness checks, not just field presence.
- `run.sh` executes regression tests and compares classifier output to independent expected decisions for every fixture; it writes `expected_output/matrix.json` from the actual run.

Sources checked 2026-10-01:

- [Cloudflare Error 1005](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1005/): owner ASN blocking, visitor/owner resolution.
- [Cloudflare Error 403](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/4xx-client-error/error-403/): several origin/edge causes; 403 does not by itself identify 1005.
- [Cloudflare Ray ID](https://developers.cloudflare.com/fundamentals/reference/cloudflare-ray-id/): diagnostic request metadata.
