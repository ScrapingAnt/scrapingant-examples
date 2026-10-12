using System.Globalization;
using System.Net;
using System.Text;
using System.Text.Json;
using ManagedAcquisition;

public static class OfflineChecks
{
    private const string FakeKey = "OFFLINE-KEY-NOT-A-CREDENTIAL";
    private static readonly Uri Target = new("https://example.test/catalog?region=us&query=C%23");
    // Literal expected fields are independent of ParseProduct and the HTML fixtures.
    private static readonly Product Oracle = new("CSHARP-001", "C# & HTTP", 99.95m, "USD");
    private static readonly string Raw = File.ReadAllText("fixtures/raw.html");
    private static readonly List<string> Passed = [];
    private static readonly List<object> Records = [];

    public static async Task RunAsync()
    {
        Console.WriteLine("OFFLINE: fake HTTP handler only; no API or target requests");
        foreach (var browser in new[] { false, true })
        {
            var handler = new FakeHandler((request, _) =>
            {
                Equal(request.Method, HttpMethod.Get);
                Equal(request.RequestUri!.GetLeftPart(UriPartial.Path), "https://api.scrapingant.com/v2/general");
                var parameters = request.RequestUri.Query.TrimStart('?').Split('&').Select(pair => pair.Split('=', 2))
                    .ToDictionary(pair => Uri.UnescapeDataString(pair[0]), pair => Uri.UnescapeDataString(pair[1]));
                Equal(parameters.Count, 6);
                Equal(parameters["url"], Target.AbsoluteUri);
                Equal(parameters["browser"], browser ? "true" : "false");
                Equal(parameters["timeout"], "30");
                Equal(parameters["proxy_type"], "datacenter");
                Equal(parameters["proxy_country"], "us");
                Equal(parameters["return_page_source"], "false");
                Equal(request.Headers.GetValues("x-api-key").Single(), FakeKey);
                Require(!request.RequestUri.AbsoluteUri.Contains(FakeKey, StringComparison.Ordinal));
                return Task.FromResult(Html(browser ? File.ReadAllText("fixtures/rendered.html") : Raw,
                    credits: browser ? "10" : "1"));
            });
            var result = await Client(handler).FetchAsync(Target, browser, CancellationToken.None);
            Equal(result.Product, Oracle); Equal(result.Attempts, 1); Equal(result.Credits, browser ? 10 : 1);
            Records.Add(new { mode = browser ? "rendered" : "raw", sku = result.Product.Sku,
                title = result.Product.Title, price = result.Product.Price, currency = result.Product.Currency,
                credits = result.Credits, attempts = result.Attempts });
            Pass($"{(browser ? "rendered" : "raw")} request shape, encoded URL, key header and literal field oracle");
            Console.WriteLine($"SIMULATED {(browser ? "rendered" : "raw")}: CSHARP-001 | C# & HTTP | 99.95 | USD; credits={result.Credits}");
        }
        await ContentCase("raw application shell has no product", File.ReadAllText("fixtures/shell.html"));
        await ContentCase("malformed non-HTML content rejected", "{bad-json");
        await ContentCase("missing price rejected", Raw.Replace("<span class=\"price\">99.95</span>", ""));
        await ContentCase("invalid decimal rejected", Raw.Replace("99.95", "9,9.95"));
        await ContentCase("negative price rejected", Raw.Replace("99.95", "-1"));
        await ContentCase("missing title rejected", Raw.Replace("C# &amp; HTTP", ""));
        await ContentCase("invalid currency rejected", Raw.Replace("USD", "usd"));
        await ContentCase("currency trailing newline rejected", Raw.Replace("data-currency=\"USD\"", "data-currency=\"USD\n\""));
        await ContentCase("duplicate products rejected", Raw.Replace("</body>", "<article data-sku=\"SECOND\"></article></body>"));
        await RejectedResponse("missing target status rejected", Html(Raw, targetStatus: null));
        await RejectedResponse("target 403 under API 200 rejected", Html(Raw, targetStatus: "403"));
        await RejectedResponse("JSON content type rejected", Html(Raw, mediaType: "application/json"));
        var absentType = new FakeHandler((_, _) => Task.FromResult(Html(Raw, mediaType: null)));
        Equal((await Client(absentType).FetchAsync(Target, false, CancellationToken.None)).Product, Oracle);
        Pass("absent content type accepted only with checked HTML schema");
        var sourceShape = Html(Raw, mediaType: null);
        sourceShape.Headers.Add("Ant-original-header-content-type", "Text/HTML; charset=utf-8");
        var sourceHandler = new FakeHandler((_, _) => Task.FromResult(sourceShape));
        Equal((await Client(sourceHandler).FetchAsync(Target, false, CancellationToken.None)).Product, Oracle);
        Pass("source-shaped success: no outer type, original target HTML type");
        var nonHtmlTarget = Html(Raw);
        nonHtmlTarget.Headers.Add("Ant-original-header-content-type", "application/json");
        await RejectedResponse("original non-HTML type overrides outer HTML type", nonHtmlTarget);
        var invalidType = Html(Raw);
        invalidType.Headers.Add("Ant-original-header-content-type", "not a media type");
        await RejectedResponse("malformed original target type rejected", invalidType);
        await RejectedResponse("no content type cannot admit non-HTML body", Html("{}", mediaType: null));
        await RejectedResponse("malformed credit receipt rejected", Html(Raw, credits: "unknown"));
        await RejectedResponse("negative credit receipt rejected", Html(Raw, credits: "-1"));
        var duplicateReceipt = Html(Raw); duplicateReceipt.Headers.Add("Ant-credits-cost", "10");
        await RejectedResponse("duplicate credit receipts rejected", duplicateReceipt);
        await ContentCase("oversized response rejected", new string('x', 1_048_577));
        await RejectedResponse("missing credit receipt rejected; cost remains unknown", Html(Raw, credits: null));

        foreach (var status in new[] { 400, 403, 404, 405, 409, 422, 423, 429 })
        {
            var pauses = new List<TimeSpan>();
            var handler = new FakeHandler((_, _) => Task.FromResult(Error(status, "synthetic detail " + FakeKey)));
            var failure = await Throws<ApiFailure>(() => Client(handler, pauses).FetchAsync(Target, false, CancellationToken.None));
            Equal(failure.Status, status); Equal(handler.Calls, 1); Equal(pauses.Count, 0);
            Require(!failure.ToString().Contains(FakeKey, StringComparison.Ordinal));
            Pass($"HTTP {status} stops once; no retry or key disclosure");
        }
        foreach (var pair in new[] {
            ("Requests quota limit reached", "quota; pause and check allowance"),
            ("Access denied from this IP address", "IP access; check whitelist"),
            ("API token is wrong", "authentication; check key locally") })
        {
            var handler = new FakeHandler((_, _) => Task.FromResult(Error(403, pair.Item1 + FakeKey)));
            var failure = await Throws<ApiFailure>(() => Client(handler).FetchAsync(Target, false, CancellationToken.None));
            Equal(failure.Category, pair.Item2); Equal(handler.Calls, 1); Pass($"403 detail category: {pair.Item2.Split(';')[0]}");
        }
        foreach (var pair in new[] {
            ("array", "[]"), ("null", "null"), ("string", JsonSerializer.Serialize("private " + FakeKey)),
            ("invalid JSON", "{broken " + FakeKey), ("non-string detail", "{\"detail\":[1]}") })
        {
            var handler = new FakeHandler((_, _) => Task.FromResult(new HttpResponseMessage(HttpStatusCode.Forbidden)
                { Content = new StringContent(pair.Item2, Encoding.UTF8, "application/json") }));
            var failure = await Throws<ApiFailure>(() => Client(handler).FetchAsync(Target, false, CancellationToken.None));
            Equal(failure.Status, 403); Equal(failure.Category, "access; inspect detail privately");
            Equal(handler.Calls, 1); Require(!failure.ToString().Contains(FakeKey, StringComparison.Ordinal));
            Pass($"{pair.Item1} error body becomes sanitized API failure");
        }
        var retryDelays = new List<TimeSpan>();
        FakeHandler? recover = null;
        recover = new FakeHandler((_, _) => Task.FromResult(recoverResponse()));
        HttpResponseMessage recoverResponse() => recover!.Calls switch { 1 => Error(502, "synthetic"), 2 => Error(503, "synthetic"), _ => Html(Raw) };
        var recovered = await Client(recover, retryDelays).FetchAsync(Target, false, CancellationToken.None);
        Equal(recovered.Product, Oracle); Equal(recovered.Attempts, 3); Equal(recover.Calls, 3);
        Require(retryDelays.SequenceEqual(new[] { TimeSpan.FromSeconds(1), TimeSpan.FromSeconds(2) }));
        Pass("502 then 503 then success: three attempts, 1s/2s scheduled delays");
        foreach (var status in new[] { 500, 502, 503, 504 })
        {
            var pauses = new List<TimeSpan>();
            var handler = new FakeHandler((_, _) => Task.FromResult(Error(status, "synthetic")));
            await Throws<ApiFailure>(() => Client(handler, pauses).FetchAsync(Target, false, CancellationToken.None));
            Equal(handler.Calls, 3); Equal(pauses.Count, 2); Pass($"HTTP {status} exhaustion capped at three attempts");
        }
        var transportPauses = new List<TimeSpan>();
        var transport = new FakeHandler((_, _) => throw new HttpRequestException("private transport " + FakeKey));
        var transportError = await Throws<TransportFailure>(() => Client(transport, transportPauses).FetchAsync(Target, false, CancellationToken.None));
        Equal(transport.Calls, 3); Equal(transportPauses.Count, 2);
        Require(!transportError.ToString().Contains(FakeKey, StringComparison.Ordinal)); Pass("transport exhaustion capped and sanitized");
        var readPauses = new List<TimeSpan>();
        var interruptedBody = new FakeHandler((_, _) => {
            var response = Html(Raw); response.Content.Dispose();
            response.Content = new StreamContent(new InterruptedStream()); return Task.FromResult(response);
        });
        var readError = await Throws<TransportFailure>(() => Client(interruptedBody, readPauses).FetchAsync(Target, false, CancellationToken.None));
        Equal(interruptedBody.Calls, 3); Equal(readPauses.Count, 2);
        Require(!readError.ToString().Contains(FakeKey, StringComparison.Ordinal));
        Pass("body transport IOException capped and sanitized");
        FakeHandler? transportRecovery = null;
        transportRecovery = new FakeHandler((_, _) => transportRecovery!.Calls == 1
            ? throw new HttpRequestException("synthetic") : Task.FromResult(Html(Raw)));
        Equal((await Client(transportRecovery).FetchAsync(Target, false, CancellationToken.None)).Attempts, 2);
        Pass("transport failure then success recovers once");
        using (var cancelled = new CancellationTokenSource())
        {
            cancelled.Cancel(); var handler = new FakeHandler((_, _) => Task.FromResult(Html(Raw)));
            await Throws<OperationCanceledException>(() => Client(handler).FetchAsync(Target, false, cancelled.Token));
            Equal(handler.Calls, 0); Pass("cancellation before send makes zero attempts");
        }
        using (var cancelled = new CancellationTokenSource())
        {
            var pauses = new List<TimeSpan>();
            var handler = new FakeHandler((_, token) => { cancelled.Cancel(); token.ThrowIfCancellationRequested(); return Task.FromResult(Html(Raw)); });
            await Throws<OperationCanceledException>(() => Client(handler, pauses).FetchAsync(Target, false, cancelled.Token));
            Equal(handler.Calls, 1); Equal(pauses.Count, 0); Pass("cancellation during send never retried");
        }
        using (var cancelled = new CancellationTokenSource())
        {
            var handler = new FakeHandler((_, _) => Task.FromResult(Error(503, "synthetic")));
            using var http = new HttpClient(handler);
            var client = new ManagedClient(http, FakeKey, (_, token) => { cancelled.Cancel(); return Task.FromCanceled(token); });
            await Throws<OperationCanceledException>(() => client.FetchAsync(Target, false, cancelled.Token));
            Equal(handler.Calls, 1); Pass("cancellation during backoff prevents replacement send");
        }
        using (var cancelled = new CancellationTokenSource())
        {
            var handler = new FakeHandler((_, _) => {
                var response = Html(Raw); response.Content.Dispose();
                response.Content = new StreamContent(new CancelStream(cancelled)); return Task.FromResult(response);
            });
            await Throws<OperationCanceledException>(() => Client(handler).FetchAsync(Target, false, cancelled.Token));
            Equal(handler.Calls, 1); Pass("cancellation during body read never retried");
        }
        var oneAttempt = new FakeHandler((_, _) => Task.FromResult(Error(503, "synthetic")));
        await Throws<ApiFailure>(() => Client(oneAttempt).FetchAsync(Target, false, CancellationToken.None, maxAttempts: 1));
        Equal(oneAttempt.Calls, 1); Pass("live-style one-attempt budget disables retries");
        var invalid = new FakeHandler((_, _) => Task.FromResult(Html(Raw)));
        await Throws<ArgumentOutOfRangeException>(() => Client(invalid).FetchAsync(Target, false, CancellationToken.None, 4));
        await Throws<ArgumentException>(() => Client(invalid).FetchAsync(new Uri("http://example.test"), false, CancellationToken.None));
        Equal(invalid.Calls, 0); Pass("invalid attempt limit and target stop before send");
        using (var http = new HttpClient(invalid))
            await Throws<ArgumentException>(() => new ManagedClient(http, " ").FetchAsync(Target, false, CancellationToken.None));
        Equal(invalid.Calls, 0); Pass("missing key stops before send");
        var disposed = new TrackingContent(Raw);
        var disposeResponse = Html(Raw); disposeResponse.Content.Dispose(); disposeResponse.Content = disposed;
        var disposeHandler = new FakeHandler((_, _) => Task.FromResult(disposeResponse));
        await Client(disposeHandler).FetchAsync(Target, false, CancellationToken.None);
        Require(disposed.Disposed); Pass("successful response content disposed");
        var errorDisposed = new TrackingContent("{}");
        var errorResponse = Error(403, "synthetic"); errorResponse.Content.Dispose(); errorResponse.Content = errorDisposed;
        await Throws<ApiFailure>(() => Client(new FakeHandler((_, _) => Task.FromResult(errorResponse))).FetchAsync(Target, false, CancellationToken.None));
        Require(errorDisposed.Disposed); Pass("error response content disposed");
        Require(ManagedClient.ParseProduct(Raw.Replace("99.95", "0")) != Oracle);
        Require(ManagedClient.ParseProduct(Raw.Replace("CSHARP-001", "OTHER")) != Oracle);
        Pass("literal oracle catches valid-shaped wrong price and SKU");
        using var oracleFile = JsonDocument.Parse(File.ReadAllText("fixtures/oracle.json"));
        Equal(oracleFile.RootElement.GetProperty("sku").GetString(), Oracle.Sku);
        Equal(oracleFile.RootElement.GetProperty("title").GetString(), Oracle.Title);
        Equal(oracleFile.RootElement.GetProperty("price").GetDecimal(), Oracle.Price);
        Equal(oracleFile.RootElement.GetProperty("currency").GetString(), Oracle.Currency);
        Pass("committed JSON oracle agrees with independent literals");
        Directory.CreateDirectory("actual_output");
        File.WriteAllText("actual_output/results.json", JsonSerializer.Serialize(new { scope = "offline-synthetic", cases = Passed.Count, records = Records }, new JsonSerializerOptions { WriteIndented = true }) + "\n");
        Console.WriteLine($"PASS {Passed.Count}/{Passed.Count} offline cases; live API calls=0");
    }
    private static async Task ContentCase(string name, string html) => await RejectedResponse(name, Html(html));
    private static async Task RejectedResponse(string name, HttpResponseMessage response)
    {
        var handler = new FakeHandler((_, _) => Task.FromResult(response));
        await Throws<ContentFailure>(() => Client(handler).FetchAsync(Target, false, CancellationToken.None));
        Equal(handler.Calls, 1); Pass(name);
    }
    private static ManagedClient Client(FakeHandler handler, List<TimeSpan>? pauses = null) => new(new HttpClient(handler), FakeKey,
        (duration, token) => { token.ThrowIfCancellationRequested(); pauses?.Add(duration); return Task.CompletedTask; });
    private static HttpResponseMessage Html(string html, string? credits = "1", string? targetStatus = "200", string? mediaType = "text/html")
    {
        var response = new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent(html, Encoding.UTF8) };
        response.Content.Headers.ContentType = mediaType is null ? null : new(mediaType);
        if (credits is not null) response.Headers.Add("Ant-credits-cost", credits);
        if (targetStatus is not null) response.Headers.Add("Ant-page-status-code", targetStatus);
        return response;
    }
    private static HttpResponseMessage Error(int status, string detail) => new((HttpStatusCode)status)
        { Content = new StringContent(JsonSerializer.Serialize(new { detail }), Encoding.UTF8, "application/json") };
    private static void Pass(string name) { Passed.Add(name); Console.WriteLine("PASS " + name); }
    private static void Require(bool condition) { if (!condition) throw new Exception("Offline assertion failed"); }
    private static void Equal<T>(T actual, T expected) => Require(EqualityComparer<T>.Default.Equals(actual, expected));
    private static async Task<T> Throws<T>(Func<Task<Acquisition>> call) where T : Exception
    {
        try { await call(); } catch (T exception) { return exception; }
        throw new Exception("Expected " + typeof(T).Name);
    }
    private sealed class FakeHandler(Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> send) : HttpMessageHandler
    {
        public int Calls { get; private set; }
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken token)
        { Calls++; return send(request, token); }
    }
    private sealed class TrackingContent(string body) : StringContent(body, Encoding.UTF8, "text/html")
    {
        public bool Disposed { get; private set; }
        protected override void Dispose(bool disposing) { Disposed = true; base.Dispose(disposing); }
    }
    private sealed class CancelStream(CancellationTokenSource source) : MemoryStream
    {
        public override ValueTask<int> ReadAsync(Memory<byte> buffer, CancellationToken cancellationToken = default)
        { source.Cancel(); return ValueTask.FromCanceled<int>(cancellationToken); }
    }
    private sealed class InterruptedStream : MemoryStream
    {
        public override ValueTask<int> ReadAsync(Memory<byte> buffer, CancellationToken cancellationToken = default)
            => ValueTask.FromException<int>(new IOException("private body transport " + FakeKey));
    }
}
