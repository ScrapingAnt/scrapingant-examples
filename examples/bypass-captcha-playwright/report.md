# Playwright CAPTCHA approaches — September 23, 2026

The useful distinction is between **avoiding a challenge**, **detecting a widget**, **obtaining a token**, and **having the target accept a submission**. A browser-detector pass or HTTP200 does not join those stages automatically.

## Recommendation

For your own application, use provider test keys and validate the full form flow. This was the only fully accepted end-to-end path in this experiment, and it was intentionally test mode.

For the next funded Python experiment, prioritize the official [2Captcha SDK](https://github.com/2captcha/2captcha-python), with [Anti-Captcha's SDK](https://github.com/anti-captcha/anticaptcha-python) as a comparison. Both installed successfully. 2Captcha2.1.1 includes `AsyncTwoCaptcha`; Anti-Captcha's tested entry point is synchronous, so an async Playwright application must avoid blocking its event loop. No service accuracy or latency ranking is possible without funded trials.

For Node, [the reCAPTCHA plugin](https://github.com/berstend/puppeteer-extra/tree/master/packages/puppeteer-extra-plugin-recaptcha) successfully discovered Google's demo widget with current Playwright. Its `solveRecaptchas()` method reported a missing provider and returned zero solutions. It supplies orchestration; it is not a credential-free solver. A missing-provider error must not be swallowed and reported as success.

The [Python audio helper](https://github.com/Xewdy444/Playwright-reCAPTCHA) remains experimentally interesting, but all three observed workflows stopped before an accepted form submission. The installed version0.5.1 was released June10,2024. Its repository has later changes; this experiment does not claim to test its current main branch. The package's v3 helper captures a token from a browser response; that does not prove a high v3 score or acceptance by a protected application.

The official [CapSolver SDK](https://github.com/capsolver/capsolver-python) installed and exposed `solve`, but the current PyPI release1.0.7 dates to July20,2023. That age alone does not prove abandonment or incompatibility. Live API behavior remains unmeasured. Review its polling/timeout behavior when integrating, and never copy examples that print the API key.

## Measurements and limits

- Five fixture cases, each once in the initial matrix. Google test-key acceptance and Turnstile test-key acceptance reached our backend and their real verification endpoints. Missing-token, forced-invalid and forced-duplicate paths produced the expected rejections. Subsequent default-run checks validate exact error codes as well as accepted/rejected state.
- Two plain-checkbox controls: one headless and one headed. Both encountered image challenges with zero-length response tokens.
- Three audio-helper workflows: headless/one-attempt budget → `RecaptchaRateLimitError` in2.18s; headed/one-attempt budget → `RecaptchaSolveError` with a visible request for more solutions in4.18s; headed/default-five-attempt budget → `RecaptchaRateLimitError` in6.30s. These are elapsed workflow times, **not solve latencies**. A budget of five does not mean five challenges were completed. No solution was submitted to the demo server.
- One Node-plugin discovery trial: one widget found, zero returned solutions, explicit missing-provider error. Its1.05s duration measures detection/error handling, not paid solving.
- Three official paid SDKs installed/imported and had their entry-point signatures checked. Zero funded solve jobs; no account balance calls, provider prices, throughput or success rates measured.
- One later ScrapingAnt browser/datacenter fetch: API200, target200,10 credits,2399 response bytes,5.09s. Widget markup was present; a response textarea and success message were absent. No form submission or server acceptance was tested. The original missing-key preflight is retained separately.

Trials ran sequentially on one macOS host/network using fresh contexts. Ordering, shared IP reputation, headed/headless executable differences and the small sample prevent a causal or statistical ranking. We did not introduce proxy rotation, personal browser profiles, login cookies or a human solver to improve the observed result. The final headed trial checked the attempt-budget limitation; it was rate-limited, after which trials stopped.

## Why test-key success is different

[Google documents](https://developers.google.com/recaptcha/docs/faq) permissive reCAPTCHA v2 test keys. [Cloudflare documents](https://developers.cloudflare.com/turnstile/troubleshooting/testing/) deterministic pass/fail/duplicate keys and distinguishes them from production credentials. These intentionally remove production challenge uncertainty. The fixture therefore tests application wiring, not the ability to defeat a real challenge.

[Turnstile's verification documentation](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/) requires server validation. Our fixture performs that call and exposes the acceptance result, rather than asserting that a hidden textarea or rendered success tick is sufficient. The duplicate case deliberately uses the provider's dummy duplicate secret; it does not test production replay resistance.

## ScrapingAnt scope

The [CAPTCHA/Cloudflare documentation](https://docs.scrapingant.com/captcha-and-cloudflare) describes browser fingerprints, regional routing and session data. That page does not supply evidence that this particular reCAPTCHA form will be automatically solved and submitted. `06_scrapingant.py` subsequently ran locally with a key. Its captured response metadata shows a successful fetch of CAPTCHA widget markup, not an accepted protected-form workflow. No response textarea or success message was found. Automatic CAPTCHA solving remains unsupported by this experiment; a200 response must not be advertised as a solve.

## Follow-up experiment needed

Use funded provider keys and an explicit small budget on the same authorized demo. For every job, record task errors, token acquisition, submission outcome, elapsed time and charged amount where exposed; store no raw key/token. Keep per-provider task counts and browser/IP/session conditions comparable. A larger sample is required before comparing reliability. Until then, retain the SDK shortlist and the observed integration/failure results without naming a paid winner.

All external documentation accessed September23,2026. Exact registry versions/release timestamps and repository revisions are recorded in packages.json and repositories.json; public-source metadata is not evidence of successful solving.

## Free trials

See [free-trials.md](free-trials.md) for dated official offers. CapSolver advertises a trial, and Anti-Captcha advertises15 demo solves for its Chrome extension. Neither observation establishes a recurring free API quota, and no trial was redeemed here. 2Captcha explicitly says it offers no free testing period.
