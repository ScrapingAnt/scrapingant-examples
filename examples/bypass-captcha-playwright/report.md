# Playwright CAPTCHA approaches — September 23, 2026

The useful distinction is between **avoiding a challenge**, **detecting a widget**, **obtaining a token**, and **having the target accept a submission**. A browser-detector pass or HTTP200 does not join those stages automatically.

## Recommendation

For your own application, use provider test keys and validate the full form flow. Those fixtures intentionally run in test mode. Separately, four funded submissions to Google's public demo were accepted, as detailed below.

For Python token-service integration, retain the official [2Captcha SDK](https://github.com/2captcha/2captcha-python), with [Anti-Captcha's SDK](https://github.com/anti-captcha/anticaptcha-python) as a comparison. Both installed successfully and later completed two accepted demo submissions each. 2Captcha2.1.1 includes `AsyncTwoCaptcha`; Anti-Captcha's tested entry point is synchronous, so an async Playwright application must avoid blocking its event loop. These small funded trials establish that both integrations worked on this demo; they do not rank accuracy, speed or price.

For Node, [the reCAPTCHA plugin](https://github.com/berstend/puppeteer-extra/tree/master/packages/puppeteer-extra-plugin-recaptcha) successfully discovered Google's demo widget with current Playwright. Its `solveRecaptchas()` method reported a missing provider and returned zero solutions. It supplies orchestration; it is not a credential-free solver. A missing-provider error must not be swallowed and reported as success.

The [Python audio helper](https://github.com/Xewdy444/Playwright-reCAPTCHA) remains experimentally interesting, but all three observed workflows stopped before an accepted form submission. The installed version0.5.1 was released June10,2024. Its repository has later changes; this experiment does not claim to test its current main branch. The package's v3 helper captures a token from a browser response; that does not prove a high v3 score or acceptance by a protected application.

The official [CapSolver SDK](https://github.com/capsolver/capsolver-python) installed and exposed `solve`, but the current PyPI release1.0.7 dates to July20,2023. That age alone does not prove abandonment or incompatibility. No key could be obtained for this experiment, so live API behavior remains unmeasured. Review its polling/timeout behavior when integrating, and never copy examples that print the API key.

## Measurements and limits

- Five fixture cases, each once in the initial matrix. Google test-key acceptance and Turnstile test-key acceptance reached our backend and their real verification endpoints. Missing-token, forced-invalid and forced-duplicate paths produced the expected rejections. Subsequent default-run checks validate exact error codes as well as accepted/rejected state.
- Two plain-checkbox controls: one headless and one headed. Both encountered image challenges with zero-length response tokens.
- Three audio-helper workflows: headless/one-attempt budget → `RecaptchaRateLimitError` in2.18s; headed/one-attempt budget → `RecaptchaSolveError` with a visible request for more solutions in4.18s; headed/default-five-attempt budget → `RecaptchaRateLimitError` in6.30s. These are elapsed workflow times, **not solve latencies**. A budget of five does not mean five challenges were completed. No solution was submitted to the demo server.
- One Node-plugin discovery trial: one widget found, zero returned solutions, explicit missing-provider error. Its1.05s duration measures detection/error handling, not paid solving.
- Three official paid SDKs installed/imported and had their entry-point signatures checked. Later, 2Captcha and Anti-Captcha credentials authenticated and four funded tasks were created. CapSolver remained unavailable. Initial preflight outputs are retained, but they no longer describe the two tested services' execution depth.
- One later ScrapingAnt browser/datacenter fetch: API200, target200,10 credits,2399 response bytes,5.09s. Widget markup was present; a response textarea and success message were absent. No form submission or server acceptance was tested. The original missing-key preflight is retained separately.

Trials ran sequentially on one macOS host/network using fresh contexts. Ordering, shared IP reputation, headed/headless executable differences and the small sample prevent a causal or statistical ranking. We did not configure proxy rotation, personal browser profiles or login cookies. The later proxyless services use their own solver infrastructure and may use human workers; their solving environment is not the local browser environment. The final headed trial checked the attempt-budget limitation; it was rate-limited, after which trials stopped.

## Why test-key success is different

[Google documents](https://developers.google.com/recaptcha/docs/faq) permissive reCAPTCHA v2 test keys. [Cloudflare documents](https://developers.cloudflare.com/turnstile/troubleshooting/testing/) deterministic pass/fail/duplicate keys and distinguishes them from production credentials. These intentionally remove production challenge uncertainty. The fixture therefore tests application wiring, not the ability to defeat a real challenge.

[Turnstile's verification documentation](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/) requires server validation. Our fixture performs that call and exposes the acceptance result, rather than asserting that a hidden textarea or rendered success tick is sufficient. The duplicate case deliberately uses the provider's dummy duplicate secret; it does not test production replay resistance.

## ScrapingAnt scope

The [CAPTCHA/Cloudflare documentation](https://docs.scrapingant.com/captcha-and-cloudflare) describes browser fingerprints, regional routing and session data. That page does not supply evidence that this particular reCAPTCHA form will be automatically solved and submitted. `06_scrapingant.py` subsequently ran locally with a key. Its captured response metadata shows a successful fetch of CAPTCHA widget markup, not an accepted protected-form workflow. No response textarea or success message was found. Automatic CAPTCHA solving remains unsupported by this experiment; a200 response must not be advertised as a solve.

## Funded demo results

| Provider | Accepted / created tasks | SDK task-to-token time | Whole browser workflow time | Charge reported by task response |
|---|---|---|---|---|
| 2Captcha2.1.1 | 2 / 2 | 40.88s, 10.50s | 42.52s, 11.82s | Unavailable in captured SDK response |
| Anti-Captcha1.0.70 | 2 / 2 | 22.71s, 22.68s | 24.10s, 24.05s | $0.00200 each ($0.00400 combined for Anti-Captcha only) |

The task order was 2Captcha1 → Anti-Captcha1 → 2Captcha2 → Anti-Captcha2. Each invocation created exactly one task, obtained a token, injected it into a fresh Google-demo response field and submitted the form. All four new response documents contained `Verification Success` with HTTP200. Tokens and provider task IDs were not persisted. [paid-comparison.json](paid-comparison.json) links the measured outputs; screenshots show the resulting acceptance pages.

The no-cost invalid-token control returned HTTP200 with `Please verify that you are not a robot.` and no success message. Its initial assertion expected a different rejection string, then was corrected to the observed message and rerun; both outputs are retained. The final control passed. This distinction confirms why HTTP200 or token presence alone is inadequate.

Times include SDK polling and network time, not just provider worker time. The pinned 2Captcha client polls at10-second intervals; Anti-Captcha polls at1-second intervals after an initial3-second delay. Both use synchronous entry points. Transport timeouts were added around the SDKs because their HTTP calls omit them; measured processes also had an external400-second timeout. No replacement task or retry was created after a failure. Two trials per service on one public demo cannot establish production reliability, throughput, a cost winner or general bypass capability. 2Captcha cost is unknown here, so a combined spend total would be misleading. CapSolver cannot be compared without a key.

The recommendation is now stronger than import-only: both 2Captcha and Anti-Captcha are demonstrated integrations for this specific flow. Choose based on application requirements and a larger representative evaluation; the present sample supports no winner.

All external documentation accessed September23,2026. Exact registry versions/release timestamps and repository revisions are recorded in packages.json and repositories.json; public-source metadata is not evidence of successful solving.

## Free trials

See [free-trials.md](free-trials.md) for dated official offers. CapSolver advertises a trial, and Anti-Captcha advertises15 demo solves for its Chrome extension. Neither observation establishes a recurring free API quota, and no trial was redeemed here. 2Captcha explicitly says it offers no free testing period.
