# CAPTCHA handling with Playwright: dated research

Tested September 23, 2026. The latest [100-trial comparison](broad-100-report.md) contains **1,200 provider requests: 100 per provider/CAPTCHA pair**, across six cases and two providers. It extends the original 120-record cohort with 1,080 additional requests and preserves every paid failure. Results distinguish demo-server acceptance, synthetic image recognition and unverified Turnstile token delivery. The [original ten-trial report](broad-report.md) and separate four-task experiment remain historical evidence. CapSolver is unavailable without a key. **Public-demo observations do not establish a production bypass rate or an overall winning provider.**

## Earlier library comparison and four-task cohort

| Approach | Version | Execution scope | Result |
|---|---|---|---|
| Plain Playwright test-key control | 1.63.0 | Real Google/Turnstile widgets plus real Siteverify calls | Five expected paths passed: Google acceptance, local missing-token rejection, Turnstile acceptance, forced rejection, forced duplicate error |
| Plain Playwright checkbox control | 1.63.0 | Google public demo, one headed and one headless visit | Both showed image challenges; no token or submitted solution |
| `playwright-recaptcha` | 0.5.1 | Google public demo: two one-attempt trials, then one headed trial with the default five-attempt budget | No accepted workflow: headless rate-limited; first headed trial required more answers; final headed trial rate-limited |
| `playwright-extra` + `puppeteer-extra-plugin-recaptcha` | 4.3.6 + 3.6.8 | One headless public-demo discovery and missing-provider check | Found one widget/sitekey; zero solutions; correctly reported absent provider |
| `2captcha-python` | 2.1.1 | Interface checks, then two funded proxyless tasks and browser form submissions | Both tokens returned and both submissions accepted |
| `anticaptchaofficial` | 1.0.70 | Interface checks, then two funded proxyless tasks and browser form submissions | Both tokens returned and both submissions accepted |
| `capsolver` | 1.0.7 | Install/import, method signature, credential preflight | Passed interface checks; live API unavailable without a key |
| ScrapingAnt browser API | n/a | One local browser/datacenter fetch of the Google demo | API200/target200;10 credits; widget markup present, response textarea absent, no success message; no form submission tested |

See [report.md](report.md), [packages.json](packages.json), [repositories.json](repositories.json) and the dated JSON/screenshot captures. This initial cohort created four paid tasks; the six-case matrix now contains 1,200, for 1,204 across both experiments (the original 120 are included). The initial SDK preflight captures are retained as historical checks. A preflight passing does **not** mean a solve succeeded. See [paid-comparison.json](paid-comparison.json) for the later funded observations.

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

On Linux, use `python -m playwright install --with-deps chromium` to install browser system dependencies. Windows has not been tested; the live audio and paid runners use POSIX `SIGALRM`.

Default `run.sh` runs 21 offline spending/privacy/evidence assertions, checks five fixture paths and imports the three official SDKs. It needs outbound HTTPS to Google and Cloudflare, but no account secrets. It exits nonzero on an unexpected fixture result or import failure. Generated JSON goes to ignored `run_output/`; dated captures in `expected_output/` are retained. Test screenshots are regenerated under `screenshots/`, so running the checks can change these tracked captures. Only provider TEST keys are embedded in the fixture.

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

## Initial four-task funded comparison

`04_2captcha.py` and `05_anticaptcha.py` perform preflight by default, even with a key present. Only explicit `--live` creates a task, with at most one creation request per invocation and no automatic task retry. `07_capsolver.py` remains preflight-only because no CapSolver key was available.

Supply `TWOCAPTCHA_API_KEY` or `ANTICAPTCHA_API_KEY` through your environment/secret manager. These commands spend funds; do not add them to scheduled checks:

```bash
# An outer deadline supplements the runner's intended 360-second SIGALRM.
python -c 'import subprocess,sys; sys.exit(subprocess.run([sys.executable,"04_2captcha.py","--live","--trial","1"],timeout=400).returncode)'
python -c 'import subprocess,sys; sys.exit(subprocess.run([sys.executable,"05_anticaptcha.py","--live","--trial","1"],timeout=400).returncode)'
# No paid task: check that a deliberately invalid token is rejected.
python 08_demo_rejection.py
```

`--trial 2` changes the capture label; it does not request retries. The dated sequence was 2Captcha1, Anti-Captcha1, 2Captcha2, Anti-Captcha2, each in a fresh headless Chromium session. The official synchronous SDK methods obtain a proxyless token, then Playwright assigns it to the demo response field and submits the form. Acceptance requires HTTP200 and `Verification Success` in the new document. An invalid-token control returned HTTP200 with a rejection message and no success message. Thus HTTP200 alone is insufficient.

| Provider | Accepted submissions / tasks | Provider elapsed time per trial | Full workflow per trial | Reported task charge |
|---|---|---|---|---|
| 2Captcha | 2 / 2 | 40.88s; 10.50s | 42.52s; 11.82s | Not exposed in captured SDK response |
| Anti-Captcha | 2 / 2 | 22.71s; 22.68s | 24.10s; 24.05s | $0.00200 each; $0.00400 for these two tasks |

These are four observations, not success-rate estimates or a speed/price ranking. Provider time includes task creation and SDK polling (2Captcha10s interval; Anti-Captcha1s polling after its initial3s delay), so it is not pure worker time. The same browser host submits all forms, but each proxyless provider controls its own solver network.

Both pinned SDKs omit HTTP request timeouts. A scoped transport patch supplies 10-second connect and30-second read timeouts; SDK solving/polling behavior is otherwise retained. The JSON field `whole_run_deadline_seconds` records the intended SIGALRM interrupt, which can be caught by lower layers; measured invocations also had an external400-second subprocess timeout. Stopping a process does not cancel an already accepted provider task. Error output retains class/code only; raw responses, keys, tokens, task IDs, balances, cookies and worker IPs are omitted. A network ambiguity during task creation is marked explicitly, and never retried automatically.

## Separate ScrapingAnt observation

The separate ScrapingAnt probe was exercised locally after a key became available:

```bash
# Supply SCRAPINGANT_API_KEY through your environment or secret manager.
./run.sh --scrapingant
```

Without a key it exits2 and explicitly reports unavailable (preserved as the initial capture). With a key it makes one browser/datacenter request to Google's official CAPTCHA demo, records only status/credit headers, response byte count/hash and widget/token-length indicators. Raw HTML, tokens and cookies are never saved. This is a fetch observation, not a form-submission test, and cannot establish automatic solving. It uses the documented query-parameter authentication; request URLs and exception messages containing them are never logged.

See [free-trials.md](free-trials.md) for separately checked trial offers; none was redeemed during this experiment.

## Interpretation

Use provider test keys for your own application's automated tests. Both official Python service clients completed the measured demo flow. 2Captcha also exposes an async client, but these trials exercised its synchronous client; no async behavior or throughput is claimed. Keep both as integration candidates without naming a winner. The Node plugin provides useful detection/provider plumbing but still needs a funded provider. Treat the free audio helper as an experiment with observed failures. CapSolver's older Python SDK deserves an explicit compatibility/timeout check against its current API before adoption. These are engineering choices, not measured accuracy or price rankings.

No raw solution tokens, account keys, account balances, cookies, private-repository references or user profile paths are intentionally included. Public provider test keys and demo sitekeys are not credentials.

## Expanded paid matrix

See [broad-report.md](broad-report.md) for the six fixture definitions, measured counts, latency ranges, costs, negative controls, replay observations and reproduction commands. [broad-comparison.json](broad-comparison.json) is generated from the dated per-trial JSON files by `summarize_broad.py`.

`python broad_matrix.py` prints a plan without network calls. Explicit `--live --rounds 10` permits at most120 tasks in one output directory; first use `--rounds 1` for a12-task pilot, then resume in the same directory. Existing records are never automatically repeated, including failures. Use one batch controller per output directory. Each paid child has a400-second external deadline; POSIX/macOS and Linux are the supported environments. Paid matrix runs are excluded from default and recurring CI.


## Reproduce the 100-trial extension

The [expanded report](broad-100-report.md) and [summary](broad-100-comparison.json) retain all 1,200 requests, initial/added phases, ten-trial blocks, returned-solution median/p90/p95, provider failures, receipt coverage and uncharged setup diagnostics. Do not summarize a directory while its controller is running.

```bash
# Offline plan only:
python broad_matrix.py --rounds 100
# Explicit funded run; one controller per output directory:
python broad_matrix.py --live --rounds 100 --workers 12 --per-provider 6 --output run_output/broad-100
# Offline reproduction of the committed completed dataset:
python summarize_100.py --output run_output/rebuilt.json
```

A fresh output directory can create up to 1,200 paid requests. The dated run first copied its previously measured 120 records, so only 1,080 further requests were made. Preserve existing trial records, including failures and uncertain creations. `recover_setup.py` can archive only a completed fixture-setup error with provably zero provider requests/tasks and no charge or ambiguity; it retains the diagnostic before explicitly releasing that unmeasured slot. Stop the controller before any such recovery, inspect `--help`, and never use recovery to replace a paid failure.
