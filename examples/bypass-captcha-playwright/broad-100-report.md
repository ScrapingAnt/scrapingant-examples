# 100 trials per CAPTCHA case and provider — September 23, 2026

**1,200 provider task-creation requests across six cases and two providers, 100 per cell.** The first 120 records are the earlier ten-trial cohort, preserved unchanged; 1,080 additional requests extend it. The separate original four-task Google-v2 experiment is excluded, making 1,204 requests across all experiments. Paid failures are retained without replacement.

Confirmed tasks created: **1,200**; uncertain creations: **0**. The report includes **one additional, uncharged setup diagnostic**, separate from the 1,200 provider requests. That slot was manually resumed only after proving that no provider request had been sent.

| CAPTCHA | Provider | Observed outcome /100 requests | Returned-solution SDK seconds: median / p90 / p95 | Reported charges (receipt coverage) |
|---|---|---|---|---|
| reCAPTCHA v2 checkbox | 2Captcha | 100/100 accepted | 6.13 / 51.27 / 61.24; n=100 | $0.29900 (100/100) |
| reCAPTCHA v2 checkbox | Anti-Captcha | 99/100 accepted | 24.91 / 140.26 / 154.61; n=100 | $0.20000 (100/100) |
| Invisible reCAPTCHA v2 | 2Captcha | 100/100 accepted | 2.13 / 61.03 / 62.74; n=100 | $0.29900 (100/100) |
| Invisible reCAPTCHA v2 | Anti-Captcha | 100/100 accepted | 34.23 / 121.05 / 139.56; n=100 | $0.20000 (100/100) |
| reCAPTCHA v3 | 2Captcha | 100/100 accepted | 12.06 / 22.24 / 24.33; n=100 | $0.29900 (100/100) |
| reCAPTCHA v3 | Anti-Captcha | 100/100 accepted | 17.50 / 24.21 / 29.12; n=100 | $0.15000 (100/100) |
| GeeTest v4 | 2Captcha | 99/100 accepted | 11.84 / 22.94 / 34.87; n=99 | $0.29601 (99/100) |
| GeeTest v4 | Anti-Captcha | 86/100 accepted | 24.24 / 47.55 / 49.00; n=86 | $0.15480 (86/100) |
| Turnstile | 2Captcha | 100/100 tokens; unverified | 10.94 / 12.46 / 16.65; n=100 | $0.14500 (100/100) |
| Turnstile | Anti-Captcha | 100/100 tokens; unverified | 16.88 / 22.99 / 23.72; n=100 | $0.20000 (100/100) |
| Synthetic image OCR | 2Captcha | 100/100 correct | 10.52 / 11.71 / 12.04; n=100 | $0.100 (100/100) |
| Synthetic image OCR | Anti-Captcha | 100/100 correct | 8.09 / 9.17 / 13.99; n=100 | $0.06000 (100/100) |

Timings include SDK task creation and polling, for returned solutions only. Failed attempts remain in the outcome denominator and have separate timing summaries. The median averages the two middle observations for even sample sizes. Only p90/p95 use nearest rank (`ceil(p*n)`), without interpolation; no reliability inference is implied. Turnstile token delivery has no server-verification evidence. OCR uses synthetic fixtures. The remaining four cases require explicit demo-server acceptance.

[Machine-readable summary](broad-100-comparison.json) · [all trial records](expected_output/broad-100-2026-09-23/) · [100 image fixtures](fixtures/image-text/manifest.json) · [original ten-trial report](broad-report.md)

## Failure details and v3 scores

- **Anti-Captcha / reCAPTCHA v2 checkbox:** non-success outcomes `{"rejected": 1}`; provider errors `{}`; server rejections 1; incorrect OCR 0; execution exceptions `{}`.
- **2Captcha v3:** score:count distribution `0.9: 100`. Acceptance requires score ≥ 0.5, expected action `examples/v3scores`, expected hostname and boolean success.
- **Anti-Captcha v3:** score:count distribution `0.9: 100`. Acceptance requires score ≥ 0.5, expected action `examples/v3scores`, expected hostname and boolean success.
- **2Captcha / GeeTest v4:** non-success outcomes `{"error": 1}`; provider errors `{"ERROR_CAPTCHA_UNSOLVABLE": 1}`; server rejections 0; incorrect OCR 0; execution exceptions `{}`. Returned-no-solution call times: median 86.11s, range 86.11–86.11s, n=1.
- **Anti-Captcha / GeeTest v4:** non-success outcomes `{"error": 14}`; provider errors `{"ERROR_CAPTCHA_UNSOLVABLE": 1, "ERROR_TOKEN_EXPIRED": 13}`; server rejections 0; incorrect OCR 0; execution exceptions `{}`. Returned-no-solution call times: median 64.65s, range 47.64–97.24s, n=14.

## Timing by measurement phase

The first ten trials per cell ran earlier with up to 4 jobs, 2 per provider. The additional 90 used up to 12 jobs, 6 per provider, on the same host/network in a later time window. The one uncharged setup failure was recovered separately with one job and is identified in the trial records and [run provenance](expected_output/broad-100-2026-09-23/provenance.json). Pooled timings mix those workloads and times; they cannot establish a causal speed ranking. The comparison below keeps the two phases visible.

| Case / provider | Initial 10: returned-solution median seconds (n) | Added 90: median / p90 / p95 seconds (n) |
|---|---|---|
| reCAPTCHA v2 checkbox / 2Captcha | 30.75 (n=10) | 1.72 / 51.27 / 61.24; n=90 |
| reCAPTCHA v2 checkbox / Anti-Captcha | 26.10 (n=10) | 24.91 / 141.97 / 171.03; n=90 |
| Invisible reCAPTCHA v2 / 2Captcha | 10.49 (n=10) | 1.95 / 44.11 / 63.40; n=90 |
| Invisible reCAPTCHA v2 / Anti-Captcha | 32.47 (n=10) | 34.23 / 118.59 / 139.56; n=90 |
| reCAPTCHA v3 / 2Captcha | 20.58 (n=10) | 11.94 / 22.56 / 34.01; n=90 |
| reCAPTCHA v3 / Anti-Captcha | 16.83 (n=10) | 17.60 / 24.22 / 29.16; n=90 |
| GeeTest v4 / 2Captcha | 15.54 (n=10) | 11.84 / 22.80 / 32.98; n=89 |
| GeeTest v4 / Anti-Captcha | 23.02 (n=5) | 24.29 / 46.37 / 49.00; n=81 |
| Turnstile / 2Captcha | 10.46 (n=10) | 11.01 / 12.46 / 16.65; n=90 |
| Turnstile / Anti-Captcha | 13.78 (n=10) | 16.93 / 22.99 / 23.95; n=90 |
| Synthetic image OCR / 2Captcha | 10.49 (n=10) | 10.53 / 11.79 / 12.11; n=90 |
| Synthetic image OCR / Anti-Captcha | 7.84 (n=10) | 8.10 / 9.17 / 13.99; n=90 |

Ten-trial blocks for every case/provider are also retained in the JSON summary to show how outcomes vary over the run. These blocks share fixtures, host/network and provider infrastructure; they are not independent population samples.

## Costs

| Provider | Known task receipt subtotal | Coverage | Observed balance decrease |
|---|---|---|---|
| 2Captcha | $1.43801 | 599/600 | $1.43801 |
| Anti-Captcha | $0.96480 | 586/600 | $0.9626 |

Receipt amounts and balance changes are separate measurements. Missing task charges are unknown; refunds, settlement timing or other account activity can cause discrepancies. No actual account balance values, credentials, provider task IDs, raw solution tokens, worker IPs or cookies are published. The current Anti-Captcha difference is $0.00220 and remains unreconciled; $0.002 of that difference was already present in the original ten-trial cohort.

## Fixtures, controls and limits

The [fixture definitions and controls](broad-report.md#what-the-criteria-measure) are unchanged: Google v2 and invisible forms, Google v3 score verification, 2Captcha-hosted GeeTest backend verification, a public Turnstile fixture without a backend verifier, and synthetic image OCR. v3 and GeeTest use Playwright browser-context requests to the demo verifier, not a complete form-click workflow. The GeeTest fixture is hosted by one compared service. Both providers receive the same image bytes in each paired OCR trial. The original ten image bytes remain unchanged; 90 further distinct images use the same generator and seed.

The original five explicit negative-control assertions and four replay probes remain the controls; they were not repeated 100 times or counted as new paid tasks. Google’s v3 demo accepted both original immediate replays, while GeeTest rejected both. Production single-use behavior is not established by that demo result. One setup-only diagnostic browser probe overlapped the extension; it incurred no solver charge.

The same pinned synchronous clients, browser and submitting host are used: 2captcha-python 2.1.1, anticaptchaofficial 1.0.70, Playwright 1.63.0, Chromium 153.0.8010.12 and macOS 26.6.2 arm64/Python 3.12.11. The two proxyless providers control their own solver networks. SDK polling differs (2Captcha 10 seconds, Anti-Captcha native 1-second polling after its initial delay). A 400-second external child deadline bounds each workflow; termination does not cancel a provider task.

Every trial ID allows at most one provider task-creation request. Resuming keeps every provider failure and ambiguous request. Only a completed fixture-setup error with zero creation requests, zero tasks, no ambiguous creation and no recorded charge can be archived by `recover_setup.py`; it preserves the original diagnostic before releasing that unmeasured slot. Recovery is explicit, after the controller stops, with at most two setup recoveries per ID. Those extra browser attempts are included in the summary and excluded from the paid-request denominator.

CapSolver remains untested live because no key was available. The earlier single ScrapingAnt fetch, free audio failures and Node plugin discovery checks are unchanged; these provider results do not validate automatic ScrapingAnt solving or the Node plugin’s paid path.

## Reproduce and validate

Install the pinned dependencies from README.md. Supply provider keys through your environment or secret manager. Default checks create no paid tasks.

```bash
./run.sh
```

For a new explicitly funded experiment:

```bash
python broad_matrix.py --rounds 100                    # plan only; no network
python broad_matrix.py --live --rounds 100 --workers 12 --per-provider 6 --output run_output/broad-100
python summarize_100.py --input run_output/broad-100 --output run_output/summary.json
# Rebuild the committed final summary without network:
python summarize_100.py --output run_output/rebuilt.json
```

Use one controller per output directory. The dated expansion seeded its directory with the previous 120 records before starting, so it created only the missing 1,080 requests. Existing provider records must never be deleted to obtain favorable results. Run `recover_setup.py --help` for the narrow, uncharged-setup archival procedure.

Fresh [local default checks](expected_output/validation-100-2026-09-23/default-checks.json) passed: 21 offline tests, five test-key paths and three SDK preflights, with zero paid tasks. The same executable source, `8931f8f81a2dc3746822639465cc851c9693fd20`, passed [Linux CI](https://github.com/ScrapingAnt/scrapingant-examples/actions/runs/35905780623). Later changes add observations and documentation.

The final summary reproduced byte-for-byte; all 12 cells contain 100 requests and confirmed tasks, the original 120 records are unchanged, and all 100 image hashes and provider pairings were checked. Independent review verified all 1,200 records, latency arithmetic, costs and coverage of every workflow by one captured spending interval, with no remaining blocking findings. Public artifacts passed exact-credential, raw-payload, private-reference and local-path checks. [Verification metadata](verification.json) records the scope.
