# Playwright detection research — issue #19

User-authorized comparison, September 22, 2026. This is a research packet, not a published article or a universal evasion benchmark.

## Scope

Five approaches: Patchright; Python playwright-stealth; Node playwright-extra with puppeteer-extra-plugin-stealth; Rebrowser Playwright; Camoufox. Controls: plain Playwright Chrome and plain Playwright Firefox. Test sites: BrowserScan bot-detection and Sannysoft. A self-authored page records browser properties from its own script rather than from an automation framework's potentially isolated evaluation world.

`packages.json` records the latest registry versions at selection time; `repositories.json` records upstream source revisions and archive status. Python versions are frozen separately; Node has exact top-level pins and package-lock.json. Camoufox has a separate environment because its 0.5.6 wrapper requires Playwright <1.63; it resolved 1.62.0. The other Python approaches use 1.63.0. Installed Chrome 153.0.8010.53 is shared across Chromium approaches. Firefox control uses Playwright's matched Firefox 153.0. Camoufox's selected official/stable channel resolved 152.0.4-beta.30; the build is explicitly pinned for launch. These are different engines/builds, not a single-variable Firefox experiment.

## Method

- One machine/network; no proxy, accounts, reused personal profiles or stored login state.
- Fresh browser for each approach×mode×repeat. Fresh context per page. Headless and headed treated separately.
- Fixed 1440×1000 viewport. Otherwise package-default settings, except Camoufox constrained to actual host OS macos and pinned browser build. No hand-written UA/anti-automation flag overrides.
- Two BrowserScan visits per approach/mode; one Sannysoft visit per approach/mode. Repetition 2 reverses approach order. This is bounded exploratory evidence, not a randomized efficacy estimate.
- Six-second and ten-second snapshots after DOMContentLoaded; verdict/flag states checked for stability. Screenshots taken after the ten-second DOM capture. No console listener or open DevTools.
- Reading the result DOM is automation activity and is not observer-free. Both snapshots are retained. A page-load/extraction failure is an error, never a detector pass.
- BrowserScan flagged categories come from its four summary labels' computed red text color, verified against screenshots. Raw class/color and verdict are retained; analyzer rejects unfamiliar colors/schema.
- Sannysoft summary uses the table's own passed/failed/warn CSS classes. Chromium-specific rows are not a fair cross-engine total score; individual failing labels remain visible.
- The local fixture is loaded as a file URL, so its properties are descriptive and not proof of behavior on all HTTPS origins.
- Package options change multiple properties together; this comparison cannot isolate causal effects of individual patches. A normal result on either page does not measure target-site access, IP reputation, behavior classification, CAPTCHA success, or network fingerprints.

## Reproduce

Requirements: Python 3.12, Node 22, installed Google Chrome, and graphical session for headed tests. Commands below use isolated temporary environments and do not install or replace your Chrome.

```bash
python3 -m venv /tmp/pw-research-venv
/tmp/pw-research-venv/bin/python -m pip install -r requirements-chromium.txt
python3 -m venv /tmp/camoufox-research-venv
/tmp/camoufox-research-venv/bin/python -m pip install -r requirements-camoufox.txt
/tmp/camoufox-research-venv/bin/python -m playwright install firefox
/tmp/camoufox-research-venv/bin/python -m camoufox fetch official/152.0.4-beta.30
npm ci --prefix node --ignore-scripts
python3 scripts/run_matrix.py
python3 scripts/summarize.py --require-complete
```

Run from this packet directory. The orchestrator refuses to overwrite results: run a new dated copy for a new experiment. Environment variables PLAYWRIGHT_PYTHON and CAMOUFOX_PYTHON override interpreter paths. Each process is bounded to 180 seconds and each navigation 45 seconds. Browser contexts close between targets; launched browsers close on completion.

## Files

- `scripts/probe.py`, `node/probe.cjs`: adapters.
- `scripts/extract.js`: identical DOM extractor used by both runtimes.
- `fixtures/properties.html`: browser-owned property capture.
- `results/*.json`: raw observations, both snapshots and errors.
- `screenshots/*.png`: viewport captures, no personal browser profiles.
- `summary.json`: derived named checks, local properties and snapshot stability.
- `report.md`: conclusions, limitations and official sources.

Transient diagnostic-page results must not be made a monthly pass/fail gate promising that a library stays undetected. For a future article packet, local fixture execution can be deterministic CI; public detector observations require dated remeasurement.

## Completed capture audit

The final matrix has 28 valid BrowserScan captures, 14 valid Sannysoft captures and 28 local-fixture captures. All sampled check states agree between six and ten seconds; no Sannysoft warnings were observed. Two initial Node adapter serialization failures were archived in `pilot-errors/` and replaced after the main matrix; their timestamps preserve this ordering deviation. They do not count as detector failures.

Three supplemental BrowserScan visits under `layout-audit/` diagnose clipped viewport screenshots; full-page images confirm Python Navigator/Robot and Node Normal. They are not extra matrix repetitions. See the layout audit README for reproduction.
