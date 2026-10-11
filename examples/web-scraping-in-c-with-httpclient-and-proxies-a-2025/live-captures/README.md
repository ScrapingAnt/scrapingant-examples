# Owned-fixture retrieval captures — 2026-10-11

These are two genuine ScrapingAnt `/v2/general` responses for the existing
[owned delayed fixture](https://scrapingant.github.io/scrapingant-examples/fixtures/dynamic-delayed.html),
recorded on October 11, 2026. Each request was authorized and sent once, with no
redirects, automatic retries, structured extraction, or account/usage endpoint calls.
The API key and raw request/header logs are not included.

## Exact scope and request

A separate C# marker probe reused **only** `ManagedClient.BuildUri` from source commit
`2b764ba84182ca47f0abcd3d5fa1a0e8315ab947`. The linked file's SHA-256 was
`4dbe22775e0bb2f55ab0f5400806eb465c05f2b9066dffdd03f4ff397157517d`.
The probe sent its own `HttpClient` request and validated the owned page's markers
with HtmlAgilityPack 1.13.0 on .NET SDK 10.0.401/runtime 10.0.12. It did **not** invoke
`ManagedClient.FetchAsync`, the product SKU parser, or the article's optional live CLI.
The marker probe and its credential binding are not part of this public packet.

Both requests used HTTPS GET, the `x-api-key` authentication header, `timeout=30`,
`proxy_type=datacenter`, `proxy_country=us`, and `return_page_source=false`.
Raw used `browser=false`. Rendered used `browser=true` and added
`wait_for_selector=#loaded`. Each had a 95-second caller deadline and a 1 MiB byte
limit. The key was absent from the URL and evidence files.

The probe required outer status 200, `Ant-page-status-code: 200`, HTML content type,
the expected actual `Ant-credits-cost` receipt, and exact DOM markers. It checked
for credential echoes before saving accepted body bytes. `receipt.json` contains
allowlisted, sanitized metadata; `response.html` contains the accepted response bytes.

| Mode | UTC start → finish | Observed elapsed time | Actual receipt | Body bytes | Accepted marker |
|---|---|---|---|---|---|
| Raw | 21:38:22.2245140 → 21:38:23.2099210 | 985 ms | 1 credit | 752 | `#test` text `Web Scraping is hard`; no actual `#loaded` node |
| Rendered | 21:39:00.8327320 → 21:39:04.0267390 | 3193 ms | 10 credits | 796 | `#test` text `I ❤️ ScrapingAnt (after 1500 ms)`; actual `div#loaded` text `loaded` |

Raw SHA-256: `d670add5613e47f7e29d08480a1eec2b2fca04e94e18eba4628fe44e9b124e93`.
Rendered SHA-256: `f004947fad2498c56cc12f09d65d2adc9cb68f518e32a18c9aa0e54bba0e56c9`.

The JavaScript source in both bodies mentions `loaded`; a source-string match is
insufficient. Acceptance requires an actual DOM element in the rendered capture.

## Replay without requests or credentials

From the packet directory:

```bash
python3 live-captures/verify_captures.py
```

The Python 3.12.11 standard-library verifier independently checks the saved bytes,
SHA-256s, allowlisted receipt fields and literal marker expectations. It makes zero
network requests. `./run.sh` continues to run only the original offline client and
SKU-parser controls; it does not rerun these paid requests.

These two observations establish retrieval, JavaScript rendering and receipts for
this owned fixture. They do not establish end-to-end product acquisition, the public
SKU parser's behavior on live HTML, production latency or reliability, throughput,
anti-bot behavior, or plan capacity. The catalog fixtures and their 1/10 receipt
values remain authored simulations. Named-author review is pending.
