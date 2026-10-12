# C# HttpClient managed HTML acquisition

This packet supports the article at `/blog/web-scraping-in-c-with-httpclient-and-proxies-a-2025`.
Its default reproduction tests the `HttpClient` integration with `/v2/general` through
injected `HttpMessageHandler` instances. It never contacts ScrapingAnt or a target during the default run,
even if `SCRAPINGANT_API_KEY` is set. The key used by the handler is an obvious fake value.
The [October 11 marker captures](live-captures/README.md) confirm raw/rendered
retrieval and receipts through a separate BuildUri-only probe. The [October 12 native
product capture](live-captures/product-jsonld/README.md) additionally passed actual
`ManagedClient.FetchAsync` with an explicit native JSON-LD contract and exact four-field
oracle. It is an owned synthetic product; the public live CLI remains unexecuted.

## Install and reproduce

Install [.NET SDK 10.0.401 from Microsoft](https://dotnet.microsoft.com/en-us/download/dotnet/10.0)
for your platform, Python 3.12.11 and Bash. These commands use Bash on macOS or Linux;
the recorded local run is macOS and Linux CI remains a separate check. `global.json` requires that exact SDK;
the project targets `net10.0` and locks HtmlAgilityPack 1.13.0 in `packages.lock.json`.
NuGet restoration is dependency setup, not a scraping API call.

```bash
dotnet --version
./run.sh
```

The recorded SDK output is `10.0.401`. The recorded environment was macOS 26.6.2 arm64,
.NET runtime 10.0.12, and Python 3.12.11. The scoped PR workflow installs SDK 10.0.401
and Python 3.12.11 on Linux; that workflow is separate verification when CI executes.

`run.sh` restores locked dependencies, builds with warnings treated as errors, runs 58 C#
legacy cases and 62 separate native JSON-LD/CLI cases, validates each suite's two
simulated records against independent literals, runs five legacy and seven native
record mutations, replays the two saved markers and one actual native-client capture,
and rejects eight capture corruptions. It compares deterministic outputs with
`expected_output/`. None of these replays makes an API request.
`./run.sh --capture` deliberately replaces recorded outputs after the checks pass.
For a workspace-only SDK, set `DOTNET` to its executable; `DOTNET_CLI_HOME` and
`NUGET_PACKAGES` may point to local task caches. No machine-wide SDK install is required.

## Files and acceptance

- `ManagedClient.cs`: URL encoding, header authentication, explicit settings, bounded GET
  retries, HTML acquisition, target-status checks, required field extraction and receipt validation.
- `Program.cs` / `LiveOptions.cs`: offline modes and an explicit one-attempt live
  command with an optional contract selector.
- `JsonLdChecks.cs` / `verify_jsonld.py`: 62 native contract/CLI controls and a second
  independent literal oracle, separate from the original 58-case denominator.
- `OfflineChecks.cs`: fake transport and response matrix; expected values are literals,
  independent of the HTML parser and fixture markup.
- `fixtures/raw.html`: authored static catalog with one product.
- `fixtures/shell.html`: authored empty application shell; parsing finds no product.
- `fixtures/rendered.html`: authored *simulated* final DOM; no JavaScript was executed to produce it.
- `fixtures/oracle.json`: literal SKU, title, decimal price and currency.
- `verify_output.py`: a second literal output oracle plus wrong-title, wrong-price,
  missing-record, false-live-scope and invented-credit mutation controls.
- `live-captures/`: historical marker captures and the October 12 native source,
  accepted full-client response, sanitized receipts and four-field oracle. All replay
  commands are offline and key-free.

The default `ArticleFields` schema is deliberately narrow: exactly one `article[data-sku]`, a nonempty
`h1`, a decimal `.price`, and a three-letter uppercase `data-currency`.
It accepts only an HTML document response with a successful target status and a
single valid `Ant-credits-cost` receipt. A missing receipt means unknown cost and
fails acceptance. HtmlAgilityPack tolerates some malformed HTML; this validator does
not certify every document as valid HTML. Adapt the selectors and field rules for
your own permitted page before a live run.
The optional `SingleProductOfferJsonLd` contract consumes one native
`application/ld+json` script with one Product/Offer object pair. It requires the
`https://schema.org` context and string SKU/name/price/currency fields, rejecting
arrays, graphs, duplicate script/property names, malformed JSON and invalid fields.
It performs no automatic fallback or HTML transformation. Its actual owned-fixture
acceptance returned `SYNTH-000 | Synthetic product 000 | 12.34 | USD` with a real
10-credit receipt on one rendered request. Source and received documents have distinct
hashes; their native script text is identical.

The client prefers the forwarded `Ant-original-header-content-type`, with outer
Content-Type as fallback. Declared non-HTML or malformed media types are rejected;
when both are absent, the returned body must still pass the HTML document and field
schema checks. The source-shaped offline control has no outer Content-Type.

The request always sets `browser` explicitly, `timeout=30`, `proxy_type=datacenter`,
`proxy_country=us`, and `return_page_source=false`. Authentication uses the
`x-api-key` header, with no key in the URL. Error diagnostics classify `detail` locally
and print only fixed messages; raw error bodies, transport messages and keys are not printed.

The integration retries only safe GET HTTP or body-stream transport failures and outer 500/502/503/504
responses, with at most three attempts and scheduled 1s/2s delays. Tests inject a
non-sleeping delay and verify its schedule; these offline controls measure no elapsed latency.
400/403/404/405/409/422/423/429 stop without automatic retries. Cancellation before
send, during send, body read or backoff stops the operation. The CLI's 95-second
deadline and disabled redirects apply to its one deliberate live attempt. API timeout,
overall caller cancellation and target-site HTTP status are distinct controls.

## Captured ArticleFields result (offline)

```text
SIMULATED raw: CSHARP-001 | C# & HTTP | 99.95 | USD; credits=1
SIMULATED rendered: CSHARP-001 | C# & HTTP | 99.95 | USD; credits=10
PASS 58/58 offline cases; live API calls=0
PASS independent literal oracle: 2 simulated records, 4 fields each
PASS 5/5 independent oracle mutation controls
```

The receipt values 1 and 10 above are **mock header values**, matching documented retrieval
choices. They are not measured service charges. Passing 58 cases is an offline case
denominator, not a production or target success rate.

## Optional live invocation — illustrative, not executed

Use only a URL you may retrieve, with markup matching your adapted schema. Set
`SCRAPINGANT_API_KEY` through your own environment mechanism; never put it in a command,
URL, source file or log. Set `PERMITTED_URL` to that complete HTTPS URL.

```bash
dotnet run --no-restore --no-build --configuration Release -- --live "$PERMITTED_URL" raw
dotnet run --no-restore --no-build --configuration Release -- --live "$PERMITTED_URL" rendered
```

Each command sends one GET with no automatic paid retries. **Neither command was run
for this packet.** The October 11 marker probe used its own send/validation path.
The October 12 observer invoked the public FetchAsync method with the explicit native
contract; it did not execute this CLI. Replay the two marker responses with
`python3 live-captures/verify_captures.py` and the native product capture with
`python3 live-captures/product-jsonld/verify_capture.py`. Both read local files only.
The target fixtures already existed; this packet records their source and returned
bytes. No account or usage endpoint is called.

### Reproduce the explicit native contract later

For the existing owned synthetic URL, the optional selector is:

```bash
PERMITTED_URL='https://scrapingant.github.io/scrapingant-examples/fixtures/apify-continuation-v1/commerce/product-000.html'
dotnet run --no-restore --no-build --configuration Release -- --live "$PERMITTED_URL" rendered --contract single-product-offer-jsonld
```

This CLI command is illustrative and **unexecuted**. It would send one paid GET when
you provide your key. The recorded acceptance used an observer around the public
method. Native JSON-LD already appears in the static source, so this observation does
not establish JavaScript-driven product updates or a need for rendering. Other stores
and broader JSON-LD layouts require their own explicit schema and permitted validation.

## Documented choices and limits

Primary references checked October 11, 2026:
[request parameters and HTML response](https://docs.scrapingant.com/request-response-format),
[credit schedule and response receipt](https://docs.scrapingant.com/credits-cost),
[outer/target errors and safe troubleshooting](https://docs.scrapingant.com/errors).
The general endpoint returns HTML; `/v2/extract` is a separate structured-extraction
product. Raw datacenter retrieval of a non-Google page is documented at 1 credit;
JavaScript-rendered datacenter retrieval at 10 credits. The marker receipts recorded
1 and 10; the native full-client receipt recorded 10 for its one rendered request.
They confirm those owned observations; they do not measure production throughput,
reliability, plan capacity or anti-bot behavior.
UTF-8 fixture responses are the tested encoding; adapt body decoding for other target encodings.
It offers no CAPTCHA-solving claim.

Current plans are at [pricing](https://scrapingant.com/#pricing); a key is available via
[signup](https://app.scrapingant.com/signup). Plan amounts and prices are documentation
observations, not capacity proven by these checks.

The macOS SDK archive used for the recorded run came from Microsoft's official URL:
`https://builds.dotnet.microsoft.com/dotnet/Sdk/10.0.401/dotnet-sdk-10.0.401-osx-arm64.tar.gz`.
Its published SHA-512 was verified before extraction:
`69f64eb00dc045398755c440b152225d544301a345a146a16e86a56a0c52b7c94b2c331520e976dbb821f18d31930aafbd25bb85961e3517e0665414ce0cbcff`.

Drafted with AI assistance, verified with offline client/parser controls and separate
owned-fixture retrieval/full-client captures. Named-author review is pending.
