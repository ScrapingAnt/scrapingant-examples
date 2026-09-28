# Captured results — 2026-09-28

The final three-round local matrix contains **72 extraction observations**: seven complete-target cases and five expected-wrong controls, each repeated in Chrome and Firefox. All **42/42** complete-target observations passed the literal three-record oracle. All **30/30** negative-control observations matched their independently specified wrong records or stale exception and failed the complete-target oracle. All **30/30** separate diagnostics matched their specified values. Thus **102/102** total matrix observations matched their case contracts; this is not a production success-rate estimate.

| Environment | Browser | Driver | Python | Selenium | Rounds |
|---|---|---|---|---|---|
| Darwin 25.6.0 arm64 | Chrome 154.0.8037.57 | ChromeDriver 154.0.8037.57 | 3.12.10 | 4.49.0 | 3 |
| Darwin 25.6.0 arm64 | Firefox 156.0 | geckodriver 0.37.1 | 3.12.10 | 4.49.0 | 3 |

Raw records and exceptions are in `expected_output/chrome.json` and `expected_output/firefox.json`; `expected_output/summary.json` is recomputed by `summarize.py`. The standalone quickstart's real output is `expected_output/quickstart.json`.

The controls identify concrete mistakes: singular lookup returns only the first record, unscoped lookup includes the outside decoy, substring class matching includes `inactive`, presence returns empty shells, and old handles raise after replacement. Their expected failures are retained as evidence, not removed from the denominator.

Verification includes 16 offline regression tests and one real-Chrome stale-during-projection regression. They are separate from matrix observations. The real-browser regression deliberately replaces DOM nodes after the first search; it requires recovery on the second search and validates the literal records. An in-memory mutation removing stale-reference handling was rejected with `StaleElementReferenceException`; `expected_output/exploratory/stale-recovery-mutation.json` records that result. This mutation does not alter the shipped source.

The first attempted fixture launch failed before opening a browser because the execution sandbox prohibited binding a local port. Its exception metadata is retained in `expected_output/exploratory/sandbox-bind-failure.json`. The final runs used permission to bind loopback and start local browsers. Chrome's own browser sandbox remained enabled. Test-first summary failures are retained separately. None of these exploratory records enters the final 102-observation summary.

The fixture contains only three intended records and two decoys; its delayed-load trigger and replacement schedule are under test control. The frame is same-origin and the shadow root is open. Results establish these cases in these captured environments only. Source CI and independent reviewer reruns are recorded separately by the integration workflow; they are not claimed by this report.
