# Five Playwright approaches compared against BrowserScan and Sannysoft

Research for [SEO issue #19](https://github.com/ScrapingAnt/seo_optimisation/issues/19), measured September 22, 2026. This packet supports a future refresh of `/blog/playwright-scraping-undetectable`; it does not change or publish the article.

**Shortlist: Patchright for a current headed Chromium integration, Camoufox for a Firefox-based headless option, and playwright-extra plus its stealth plugin as the strongest Chromium headless result in this particular test.** Python playwright-stealth demonstrates why passing one diagnostic page is insufficient: it had no Sannysoft failed checks, while BrowserScan flagged Navigator in both modes. Rebrowser's default configuration retained the same named flags as ordinary Chrome in these suites.

These are observations of diagnostic pages, not evidence that any library is universally undetectable. Recommendations combine the measured results below with integration and version constraints.

## Packages and integration approaches

Versions are the registry releases selected on the measurement date; exact dependencies are retained in the Python freeze files and Node lockfile. Repository inspection revisions in `repositories.json` are not asserted to be the commits used to build those registry packages.

| Approach tested | Mechanism and integration | Version and selection tradeoff |
|---|---|---|
| [Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python) | Patched Playwright driver and launch behavior; change the Python import. Its upstream patches target automation leaks including Runtime/console behavior. Chromium-focused. | 1.63.0, released Sep 20, 2026. Closely matches current Playwright 1.63 in this test. Headed default worked well here; headless UA remained visible. |
| [Python playwright-stealth](https://github.com/Mattwmaster58/playwright_stealth) | JavaScript evasions around standard Playwright; tested the documented `Stealth().use_sync(sync_playwright())` wrapper. | 2.0.3, released Apr 4, 2026, on Playwright 1.63.0. Simple integration; the project's own description limits expectations to simple detections. Defaults need consistency review on the actual host. |
| [playwright-extra](https://github.com/berstend/puppeteer-extra/tree/master/packages/playwright-extra) + [puppeteer-extra-plugin-stealth](https://github.com/berstend/puppeteer-extra/tree/master/packages/puppeteer-extra-plugin-stealth) | Node plugin framework around Playwright Chromium, with JavaScript and launch-time evasions supplied by the stealth plugin. | 4.3.6 + 2.11.2, both registry releases Mar 1, 2023, with Playwright 1.63.0. Strong observed defaults, but old package releases warrant compatibility testing; age alone does not prove abandonment. |
| [Rebrowser Playwright](https://github.com/rebrowser/rebrowser-playwright) | Drop-in Node Playwright fork, with [patches](https://github.com/rebrowser/rebrowser-patches) focused on automation leaks such as Runtime.enable. Tested without adding a separate stealth plugin or custom flags. | 1.52.0, released May 9, 2025. The driver version is substantially behind the other Chromium adapters. These results apply to its tested combination with installed Chrome 153, not to every possible patched setup. |
| [Camoufox](https://github.com/daijro/camoufox) | Modified Firefox browser controlled through Playwright, with generated fingerprints and browser-level changes; Python context manager. See [usage documentation](https://camoufox.com/python/usage/). | Python 0.5.6, released Sep 6, 2026; browser 152.0.4-beta.30 pinned explicitly. Wrapper requires Playwright<1.63 and resolved 1.62.0 in its separate environment. Different engine and fingerprint defaults require separate compatibility work. |

Release dates and dependency declarations are retained with their registry URLs in [packages.json](packages.json). Camoufox's selected official/stable channel resolved a build whose version contains `beta`; the channel label does not remove that build identity. Its normal fingerprint generation/default addons were retained, with `os='macos'` and the browser build explicitly fixed. Fingerprints were not held constant across launches.

## BrowserScan: actual displayed verdicts

Target: [BrowserScan bot detection](https://www.browserscan.net/bot-detection). Each cell represents **two fresh-browser observations**. Both observations agreed in every cell. Parentheses list the page's red summary categories, not our guesses about its private detection logic.

| Configuration | Headless, 2 observations | Headed, 2 observations |
|---|---|---|
| Plain Playwright Chrome control | Robot — Webdriver, User-Agent | Robot — Webdriver |
| Patchright | Robot — User-Agent | **Normal — no red categories** |
| Python playwright-stealth | Robot — Navigator | Robot — Navigator |
| playwright-extra + stealth plugin | **Normal — no red categories** | **Normal — no red categories** |
| Rebrowser Playwright | Robot — Webdriver, User-Agent | Robot — Webdriver |
| Plain Playwright Firefox control | Robot — Webdriver | Robot — Webdriver |
| Camoufox | **Normal — no red categories** | **Normal — no red categories** |

The four collected categories were Webdriver, User-Agent, CDP and Navigator. **CDP was unflagged even for the ordinary Chrome control.** This experiment therefore cannot establish that a Patchright or Rebrowser CDP patch defeated a working positive CDP test. It records only the displayed result of this version of BrowserScan.

Representative screenshots: [Chrome headless control](screenshots/chrome-control-headless-1-browserscan.png), [Patchright headed](screenshots/patchright-headed-1-browserscan.png), [Python stealth headless, supplemental full page](layout-audit/python-stealth-headless-full.png), [Node stealth headless, supplemental full page](layout-audit/extra-stealth-headless-full.png), [Camoufox headless](screenshots/camoufox-headless-1-browserscan.png).

## Sannysoft: named failed checks

Target: [Sannysoft](https://bot.sannysoft.com/). One observation per approach/mode, with 31 recognized classified checks in each capture. “None” means none of those captured checks carried the page's `failed` CSS state. Sannysoft was not repeated on the second BrowserScan pass.

| Configuration | Headless: failed checks | Headed: failed checks |
|---|---|---|
| Plain Chrome control | User Agent (Old); WebDriver (New); HEADCHR_UA; CHR_MEMORY | WebDriver (New) |
| Patchright | User Agent (Old); HEADCHR_UA; CHR_MEMORY | None |
| Python playwright-stealth | None | None |
| playwright-extra + stealth plugin | None | None |
| Rebrowser Playwright | User Agent (Old); WebDriver (New); HEADCHR_UA; CHR_MEMORY | WebDriver (New) |
| Plain Firefox control | WebDriver (New); Chrome (New); Plugins Length (Old); Plugins is of type PluginArray | Same four checks |
| Camoufox | Chrome (New) | Chrome (New) |

The `Chrome (New)` check is Chrome-specific; its failure in Firefox is not a fair basis for calling Firefox automated. We retain the literal result instead of combining these rows into a cross-engine score. Likewise, CHR_MEMORY's name or failed state does not identify its causal relationship to bot blocking. No warning states were observed. Raw rows and descriptions remain in the JSON captures.

## What the local fixture adds

A page-owned inline script captured browser properties before the adapter read its DOM. In the first headless run, plain Chrome and Rebrowser exposed `navigator.webdriver=true`; Patchright, Python stealth and Node stealth exposed false. The Firefox control exposed true and Camoufox false.

Python stealth reported `platform: Win32` alongside a Macintosh user agent on this Mac. Its default WebGL and language values also differed from plain Chrome. BrowserScan independently flagged Navigator. That is a useful consistency warning, but this experiment did not isolate which property triggered the detector. We do not attribute the flag to `platform` alone. The Node plugin also changed fingerprint properties but did not receive that flag in these captures.

The fixture uses a local file URL. These property samples describe that page and configuration, not all HTTPS origins or all fingerprint surfaces. The retained [summary](summary.json) and [raw results](results/) include the values for each run.

## Method, controls and limits

The host was macOS 26.6.2 arm64, Python 3.12.11 and Node 22.20.0. All Chromium configurations used the same installed Google Chrome 153.0.8010.53 with `channel='chrome'`; no bundled headless shell was substituted. The ordinary Firefox control used Playwright 1.62.0's matched Firefox 153.0. Camoufox used its own 152.0.4-beta.30 build. Sharing Chrome reduces binary differences, but Rebrowser still differs in driver version. The Firefox comparison changes the browser build and fingerprint behavior together, so it is not a single-variable patch experiment. Playwright documents browser/channel differences and version-specific binaries in its [browser guide](https://playwright.dev/python/docs/browsers).

Each of 28 canonical runs launched a fresh browser, with a fresh context per page, a 1440×1000 viewport, the same machine/network, no proxy, no account cookies and no manual UA/stealth-flag tuning. Tests ran sequentially. The second repetition reversed approach order; this is not a randomized experiment. Patchright's upstream recommended persistent-context setup was not separately tested, so this is a comparison of the documented adapter configurations, not the best attainable result for each library.

The packet contains 28 BrowserScan observations, 14 Sannysoft observations and 28 local-fixture captures. Public-page DOM snapshots were taken six and ten seconds after DOMContentLoaded, followed by a viewport screenshot. No console listeners or DevTools were opened. Reading DOM through automation may itself affect a detector; the measurement is not observer-free. All captured verdict/category states agreed between the two snapshots. Stability means agreement at two sampled instants only. Viewport screenshots do not display every lower Sannysoft row; retained DOM rows support those checks. In the two JavaScript-stealth configurations, BrowserScan laid out a 4000-pixel-wide body despite a 1440-pixel viewport, placing the verdict outside the original viewport images. Three separately retained [layout-audit visits](layout-audit/README.md), two Node and one Python, captured full pages with unchanged browser settings. Those images agree with the respective DOM verdicts; the Node follow-up also recorded Normal immediately before and after screenshot collection. These supplemental visits are excluded from the 28-run comparison matrix. The layout cause was not isolated.

Two initial Node runs had a harness serialization error, so their DOM snapshots were unavailable. Their original JSON/screenshots are preserved in [pilot-errors](pilot-errors/), excluded from aggregation and replaced by fresh runs after the main matrix. Accordingly, those repaired repetition 1 runs happened after repetition 2. Errors were not counted as bot detections or passes. The fix changed the extractor invocation, not the libraries' browser configuration.

The summarizer validates recognized URLs/statuses, BrowserScan verdicts/four labels/colors, all 31 unique Sannysoft check names and exactly one known state per check. Its `--require-complete` mode rejects missing runs, page errors, missing local observations or screenshots. An independent [method review](method-review.md) checked the harness, raw observations and representative screenshots; its schema and coverage findings were addressed before final aggregation. See [README](README.md) for reproduction and exact files.

These limited repeats do not estimate a success probability. The study did not measure commercial target-site access, IP reputation, CAPTCHA solving, behavioral classification, TLS/network fingerprints, speed, resource use or long-running stability. No result establishes universal invisibility. Rebrowser's own detector and CreepJS were considered but not run; no results are claimed for them.

## Recommended direction for issue #19

1. **Use Patchright as the main current Python/Chromium worked example when headed operation is acceptable.** Show the headless UA result beside it, rather than implying the import change removes every visible signal. Any tuned headless or persistent-context recipe needs its own future evidence run.
2. **Show Camoufox as a distinct Firefox alternative for headless use.** Its BrowserScan results were normal in both modes here; evaluate the intended site's Firefox support and the pinned beta browser/dependency constraint before selecting it.
3. **Include Node playwright-extra plus stealth as a measured Chromium headless alternative.** It did well on both pages in this configuration. Its older release dates justify an explicit compatibility caveat and tests after browser updates, not dismissal of the observed result.
4. **Use Python playwright-stealth to teach cross-suite validation.** Sannysoft alone would miss the BrowserScan Navigator flag. Host-consistent configuration should be tested separately before recommending production defaults.
5. **Present Rebrowser as a targeted driver-patching option, not a complete default stealth profile.** These two suites do not demonstrate a CDP advantage, and the chosen package is pinned to an older Playwright generation.

The existing article's legacy repository now resolves to [undetected-playwright-python](https://github.com/ttlns/undetected-playwright-python), which GitHub marked archived at inspection. Replace the old Playwright 1.40 recipe and historical score-based claims with the dated comparison above. Preserve the existing URL/filename and original author, distinguish diagnostic signals from real access outcomes, and remove unsupported universal bypass/CAPTCHA promises. A future article should include a visible update note, query-level baseline and a committed article evidence packet before publication. Research completion alone does not close issue #19.
