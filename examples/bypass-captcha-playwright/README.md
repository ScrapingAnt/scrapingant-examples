# CAPTCHA handling with Playwright: dated research

Tested September 23, 2026. This packet compares browser integration approaches and records failures. **It does not establish a winning paid solver or a production CAPTCHA bypass rate.** Paid solver credentials and a ScrapingAnt key were unavailable in this run.

## What was actually executed

| Approach | Version | Execution scope | Result |
|---|---|---|---|
| Plain Playwright test-key control | 1.63.0 | Real Google/Turnstile widgets plus real Siteverify calls | Five expected paths passed: Google acceptance, local missing-token rejection, Turnstile acceptance, forced rejection, forced duplicate error |
| Plain Playwright checkbox control | 1.63.0 | Google public demo, one headed and one headless visit | Both showed image challenges; no token or submitted solution |
| `playwright-recaptcha` | 0.5.1 | Google public demo: two one-attempt trials, then one headed trial with the default five-attempt budget | No accepted workflow: headless rate-limited; first headed trial required more answers; final headed trial rate-limited |
| `playwright-extra` + `puppeteer-extra-plugin-recaptcha` | 4.3.6 + 3.6.8 | One headless public-demo discovery and missing-provider check | Found one widget/sitekey; zero solutions; correctly reported absent provider |
| `2captcha-python` | 2.1.1 | Install/import, method signature, async-client presence, credential preflight | Passed interface checks; live paid solving not run |
| `anticaptchaofficial` | 1.0.70 | Install/import, method signature, credential preflight | Passed interface checks; live paid solving not run |
| `capsolver` | 1.0.7 | Install/import, method signature, credential preflight | Passed interface checks; live paid solving not run |
| ScrapingAnt browser API | n/a | Credential preflight | Not requested: key unavailable; there is no captured API response |

See [report.md](report.md), [packages.json](packages.json), [repositories.json](repositories.json) and the dated JSON/screenshot captures. Zero paid tasks were created. A provider preflight passing does **not** mean a solve succeeded.

## Reproduce the credential-free checks

The measured environment was macOS26.6.2 arm64, Python3.12.11 and Node22.20.0. Chromium reported153.0.8010.12. Headless runs used Playwright's bundled headless shell; headed runs used its full Chromium build. Fresh contexts share the same machine/network, so these are not independent network samples.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python -m playwright install chromium
npm ci
./run.sh
```

On Linux, use `python -m playwright install --with-deps chromium` to install browser system dependencies. Windows has not been tested; the live audio runner uses POSIX `SIGALRM` for its total deadline.

Default `run.sh` checks five fixture paths and imports the three official SDKs. It needs outbound HTTPS to Google and Cloudflare, but no account secrets. It exits nonzero on an unexpected fixture result or import failure. Generated JSON goes to ignored `run_output/`; dated captures in `expected_output/` are retained. Test screenshots are regenerated under `screenshots/`, so running the checks can change these tracked captures. Only provider TEST keys are embedded in the fixture.

A failed fixture request is not a production-solver result. The forced Turnstile duplicate test uses the documented dummy secret, not a replay of a real production token. The Google test secret is deliberately permissive; missing tokens are rejected locally before Siteverify.

## Bounded public-demo observations

These are opt-in, are not part of the monthly checks, and may fail or change with browser/network state. The audio path also requires `ffmpeg` and `ffprobe` on PATH; the measured FFmpeg version is in `expected_output/ffmpeg-version.txt`. Speech transcription is sent to Google's speech-recognition service by the library; it is not local transcription. No paid CapSolver image classification is used.

```bash
python 02_playwright_recaptcha.py --baseline
python 02_playwright_recaptcha.py --baseline --headed
python 02_playwright_recaptcha.py --attempts 1
python 02_playwright_recaptcha.py --headed --attempts 1
python 02_playwright_recaptcha.py --headed --repeat 2 --attempts 5
node 03_extra_recaptcha.cjs
```

An audio/control script exits1 if no server-accepted workflow is observed, including when an image challenge remains. The plugin script exits0 only if it detects one widget and reports the expected missing-provider error; this is an integration assertion, not a solving success. The audio experiment has a90-second total deadline,15-second Playwright action timeout and an explicit attempt budget. Stop if the service rate-limits the browser; do not loop these scripts to obtain a favorable result. The dated sequence includes one later headed trial to check whether the initial one-attempt limit explained its incomplete result; that final trial was rate-limited, and testing stopped.

## Credentials and unfinished measurements

`04_2captcha.py`, `05_anticaptcha.py` and `07_capsolver.py` perform preflight only. Even if their named key is present, they do not spend funds or create a solve task. Live paid comparison remains unimplemented/unmeasured in this packet; a funded trial must validate the target's submission result, not just log a token.

The separate ScrapingAnt probe is prepared but has **not been exercised with a key**:

```bash
# Supply SCRAPINGANT_API_KEY through your environment or secret manager.
./run.sh --scrapingant
```

Without a key it exits2 and explicitly reports unavailable. With a key it makes one browser/datacenter request to Google's official CAPTCHA demo, records status/credit headers, widget/token indicators and a redacted response. This is a fetch observation, not a form-submission test, and cannot establish automatic solving. It uses the documented query-parameter authentication; request URLs and exception messages containing them are never logged. Inspect generated output for sensitive data before sharing it.

## Interpretation

Use provider test keys for your own application's automated tests. For a future paid Python trial, the current official 2Captcha SDK is the first integration candidate: its published release is recent and it exposes an async client. Keep Anti-Captcha as a second service candidate. The Node plugin provides useful detection/provider plumbing but still needs a funded provider. Treat the free audio helper as an experiment with observed failures. CapSolver's older Python SDK deserves an explicit compatibility/timeout check against its current API before adoption. These are engineering choices, not measured accuracy or price rankings.

No raw solution tokens, account keys, account balances, cookies, private-repository references or user profile paths are intentionally included. Public provider test keys and demo sitekeys are not credentials.
