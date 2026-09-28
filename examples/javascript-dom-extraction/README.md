# Extract DOM records inside a ScrapingAnt JavaScript snippet

This packet tests a small transport protocol: the browser extracts data, writes JSON into one `script[type="application/json"]` element, and the client reads that element from the returned HTML. It supports the Selenium, Playwright and Puppeteer element-extraction articles. It is not a benchmark of production scraping reliability.

## Free local reproduction

Use Python 3.12 and Node 22. The default command never calls ScrapingAnt, even if an API key is configured.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
npm ci
./run.sh
```

The command runs 21 Python regression methods, 8 Node tests and 6 browser cases against a loopback HTTP server. Fresh outputs go to ignored `run_output/`. Committed captures stay in `expected_output/`. The regression suite also parses saved live responses; that reads files, not the API. Dependency/browser installation may need Internet access.

The local server sends HTML as UTF-8. The first run without an explicit charset produced mojibake in the delayed fixture, and the literal oracle rejected it. That capture is retained in `expected_output/exploratory/local-missing-charset.json`, outside the final denominator.

## Live reproduction: explicit paid opt-in

Set `SCRAPINGANT_API_KEY` in your environment without putting it in source control. Inspect the plan first:

```bash
python live_probe.py
python live_probe.py --live
```

`--live` sends exactly six requests to two fixed, self-authored public fixtures. It has no retry loop, disables redirects, sends the key only in the API authentication header, and refuses to overwrite an existing report. Browser rendering and datacenter mode are explicit. The recorded run used 10 credits for each response, totaling 60; check current [credit documentation](https://docs.scrapingant.com/credits-cost) before another run. HTTP errors and connection exceptions save only statuses/classes, never raw exception strings or request URLs. The API key is not sent to fixture origins.

| Case | Purpose | Recorded outcome |
|---|---|---|
| `catalog_1`–`catalog_3` | Select `#prices tbody tr`, project four fields, carry JSON through HTML | Three complete extractions, three records each |
| `return_only` | Return a JavaScript object without changing the DOM | HTTP 200, no result marker |
| `missing_selector` | Extract a selector absent from the fixture | HTTP 200, valid envelope with `ok: false` and `ELEMENT_MISSING` |
| `delayed` | Wait for the fixture's `#loaded`, read populated text, await a further operation | Expected delayed text and `awaited: true` |

All six calls returned HTTP 200. Four produced successful data envelopes, one an explicit extraction error, and one no marker by design. All six matched their specific expected outcomes. Do not describe this as a six-of-six production extraction success rate. The three catalog repeats share one target, one run window and one implementation. The other cases are diagnostics, not catalog attempts.

The `catalog` cases also insert and read a synthetic DOM text probe containing `</script>`, `<!--<script>`, literal `&amp;`, quotes, backslashes, a newline, Ukrainian, Chinese, emoji and Unicode line separators. This probe tests transport; it is not catalog data. Both Python parsers and the Node parser recovered the exact characters from all three live responses.

Public fixture sources are copied byte-for-byte under `fixtures/`; `fixture-check.json` records their successful fetch and SHA-256 comparison. Actual responses and receipts are in `expected_output/live/`. Request details contain only fixed public targets, random framing identifiers and non-secret extraction configuration.

## Why DOM JSON rather than `return records`?

The [general endpoint](https://docs.scrapingant.com/request-response-format) returns page HTML. The live return-only control demonstrates that a snippet's returned object did not become that response. `snippet.js` instead builds a versioned envelope and appends a carrier element. The `__CONFIG__` placeholder is filled by `state.snippet()` using JSON serialization; do not send the template unchanged.

The carrier-writing code is:

```javascript
const carrier = document.createElement("script");
carrier.id = config.marker;
carrier.type = "application/json";
carrier.textContent = JSON.stringify(result).replace(/</g, "\\u003c");
document.body.append(carrier);
```

Escaping `<` stops data such as `</script>` from closing the raw-text carrier when returned HTML is parsed. Use a literal JSON `\u003c` escape, not `\x3c`. Do not HTML-escape the JSON or entity-decode it on the client: `&amp;` is literal data here.

Generate a unique `sa-extract-` plus 32 lowercase hexadecimal characters for each request. The nonce avoids accidental collisions; it does not authenticate data against a hostile page. The page and its scripts still control their browser environment.

## Parse and validate the response

`protocol.parse_html()` is the preferred Python parser: it accepts normalized attribute order while requiring exactly one matching script with the expected type. `protocol.parse_marker()` and `parse-marker.mjs` cross-check a real HTML parse before demonstrating the requested exact-marker regex approach. They deliberately accept only the opening tag generated above and fail if its formatting changes. The Node implementation uses pinned `parse5` for that DOM check. This regex is a framing protocol, not a general-purpose HTML parser.

Parse one saved response in Node (the command reads its marker from the receipt):

```bash
node --input-type=module -e 'import fs from "node:fs"; import {parseMarker} from "./parse-marker.mjs"; const run=JSON.parse(fs.readFileSync("expected_output/live/live.json","utf8")); console.log(JSON.stringify(parseMarker(fs.readFileSync("expected_output/live/catalog_1.html","utf8"),run.calls[0].marker),null,2));'
```

The exact parser implementation is in [parse-marker.mjs](parse-marker.mjs). Both clients reject missing/duplicate carriers, invalid JSON, unsupported versions and wrong envelope shapes. Python additionally rejects duplicate JSON object keys; native Node `JSON.parse` does not provide that check. The producer uses `JSON.stringify` on ordinary objects. A valid `ok: false` envelope is an extraction failure, separate from a transport/parser failure. After `ok: true`, validate application fields and completeness: the protocol itself does not know which records you intended to scrape.

`state.py` contains three independent literal expected record dictionaries. `summarize.py` reparses saved HTML, compares each field and record order, reruns the Node parser, checks the full case inventory and recomputes credit totals. It rejects forged success flags, changed records, omitted cases and receipt inconsistencies.

```bash
python summarize.py
python verify.py
```

`comparison.json` is the saved recomputed result. Source/artifact hashes are in `verification.json`. Changing a captured response or runtime source requires review and a new evidence snapshot, not merely changing a success flag.

## Conditions and limits

- [Custom JavaScript](https://docs.scrapingant.com/javascript-execution) runs with `browser=true`; encode UTF-8 JavaScript as standard Base64, then use normal query-parameter URL encoding. Keep `return_page_source=false` to receive DOM changes.
- The HTML endpoint carries the result. This packet does not test the Markdown endpoint or arbitrary returned JavaScript values.
- The delayed case uses a selector already created by the page, `#loaded`. Do not configure the service to wait for your snippet's result marker. The snippet checks semantic readiness and stays within a bounded wait.
- The API's documented 60-second maximum request budget includes page work; it is not an extra 60 seconds for your snippet.
- This is one-page extraction. Multi-step sessions, pagination, closed shadow roots, cross-origin frames, anti-bot success, payload-size limits and production uptime were not measured.
- Browser JavaScript here uses native DOM selectors; Playwright/Puppeteer-specific locator syntax is not automatically available inside a snippet.
- No localStorage operation or storage-state import is tested or implied.

Primary references checked 2026-09-28: [ScrapingAnt JavaScript execution](https://docs.scrapingant.com/javascript-execution), [request/response format](https://docs.scrapingant.com/request-response-format), [HTML script data restrictions](https://html.spec.whatwg.org/multipage/scripting.html#restrictions-for-contents-of-script-elements), [JSON.stringify](https://tc39.es/ecma262/multipage/structured-data.html#sec-json.stringify). AI assisted implementation; measurements come from the saved executions.
