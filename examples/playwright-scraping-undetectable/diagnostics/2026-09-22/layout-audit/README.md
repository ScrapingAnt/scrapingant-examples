# Supplemental screenshot layout audit

The canonical viewport screenshots for the Python and Node stealth configurations clipped BrowserScan's results to the right. Fresh headless visits measured a body/document width of 4000 pixels and a 1440-pixel viewport. The Test Results heading began around x=1840. No page CSS or browser settings were changed to fix the layout; full-page screenshots captured it as rendered.

- `python-stealth-headless.json` and its full PNG: Robot, Navigator red.
- `extra-stealth-headless.json` and its full PNG: Normal, all four labels white.
- `post-capture-check/extra-stealth-headless.json` adds observations immediately before and after the full-page screenshot: all remained Normal. Its PNG is byte-identical to the first Node full-page PNG.

These three additional visits are separate from the canonical 28-run matrix. A preliminary visual concern when comparing the very similar wide images was resolved by individual inspection and an independent reviewer; the stored Node images and DOM do not contradict one another. The body-width cause was not isolated.

Reproduce from a new dated packet copy, after installing dependencies:

```bash
/tmp/pw-research-venv/bin/python scripts/capture_layout.py
node node/capture_layout.cjs
```

The current Node script writes `post-capture-check/` and includes the added before/after observations. The first Node audit used the same setup without these two additional extraction calls.
