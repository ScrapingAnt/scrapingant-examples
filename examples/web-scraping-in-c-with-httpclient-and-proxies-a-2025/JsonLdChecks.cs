using System.Net;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using ManagedAcquisition;

public static class JsonLdChecks
{
    private const string FakeKey = "JSONLD-OFFLINE-NOT-A-CREDENTIAL";
    private static readonly Uri Target = new("https://scrapingant.github.io/scrapingant-examples/fixtures/apify-continuation-v1/commerce/product-000.html");
    // Literals do not come from the parser, source HTML or service output.
    private static readonly Product Oracle = new("SYNTH-000", "Synthetic product 000", 12.34m, "USD");
    private static readonly List<string> Passed = [];
    private static readonly List<object> Records = [];
    private const ProductContract Contract = ProductContract.SingleProductOfferJsonLd;

    public static async Task RunAsync()
    {
        Console.WriteLine("OFFLINE JSON-LD: saved owned bytes and fake HTTP handlers; no key lookup or requests");
        string source = File.ReadAllText("live-captures/product-jsonld/source-response.html");
        string rendered = File.ReadAllText("live-captures/product-jsonld/response.html");
        Equal(ManagedClient.ParseProduct(source, Contract), Oracle);
        Equal(ManagedClient.ParseProduct(rendered, Contract), Oracle);
        Pass("native source and managed response match independent four-field literals");
        Reject("ArticleFields does not silently fall back to JSON-LD", source, ProductContract.ArticleFields);
        Reject("JSON-LD does not silently fall back to article attributes", File.ReadAllText("fixtures/raw.html"));
        const string valid = "{\"@context\":\"https://schema.org\",\"@type\":\"Product\",\"sku\":\"SYNTH-000\",\"name\":\"Synthetic product 000\",\"offers\":{\"@type\":\"Offer\",\"price\":\"12.34\",\"priceCurrency\":\"USD\"}}";
        foreach (var pair in new[] { ("array root", "[]"), ("null root", "null"), ("string root", "\"text\""),
            ("number root", "1"), ("malformed JSON", "{bad") }) Reject(pair.Item1 + " rejected", Html(pair.Item2));
        Reject("non-HTML body rejected", valid);
        Reject("missing JSON-LD script rejected", "<html><body></body></html>");
        Reject("multiple JSON-LD scripts rejected", Html(valid).Replace("</body>", Script(valid) + "</body>"));
        foreach (var mutation in new[] { "context", "type", "type-list", "offers-array", "offers-null", "offer-type",
            "sku", "name", "price", "currency", "numeric-price", "negative-price", "bad-price", "lower-currency",
            "blank-title", "blank-sku", "graph" })
        {
            var json = JsonNode.Parse(valid)!.AsObject();
            switch (mutation)
            {
                case "context": json["@context"] = "http://schema.org"; break;
                case "type": json["@type"] = "Thing"; break;
                case "type-list": json["@type"] = new JsonArray("Product"); break;
                case "offers-array": json["offers"] = new JsonArray(json["offers"]!.DeepClone()); break;
                case "offers-null": json["offers"] = null; break;
                case "offer-type": json["offers"]!["@type"] = "AggregateOffer"; break;
                case "sku": json.Remove("sku"); break;
                case "name": json.Remove("name"); break;
                case "price": json["offers"]!.AsObject().Remove("price"); break;
                case "currency": json["offers"]!.AsObject().Remove("priceCurrency"); break;
                case "numeric-price": json["offers"]!["price"] = 12.34; break;
                case "negative-price": json["offers"]!["price"] = "-1"; break;
                case "bad-price": json["offers"]!["price"] = "12.34 USD"; break;
                case "lower-currency": json["offers"]!["priceCurrency"] = "usd"; break;
                case "blank-title": json["name"] = " "; break;
                case "blank-sku": json["sku"] = " "; break;
                case "graph": json = new JsonObject { ["@graph"] = new JsonArray(json.DeepClone()) }; break;
            }
            Reject(mutation + " rejected", Html(json.ToJsonString()));
        }
        Reject("duplicate SKU property rejected", Html(valid.Replace("\"sku\":", "\"sku\":\"wrong\",\"sku\":")));
        Reject("duplicate price property rejected", Html(valid.Replace("\"price\":", "\"price\":\"0\",\"price\":")));
        Reject("currency trailing newline rejected", Html(valid.Replace("\"USD\"", "\"USD\\n\"")));
        Reject("graph alongside Product rejected", Html(valid.Replace("\"sku\":", "\"@graph\":[],\"sku\":")));
        Reject("unsupported contract rejected", source, (ProductContract)(-1));
        foreach (var mode in new[] { "raw", "rendered" })
        {
            Require(LiveOptions.TryParse(["--live", Target.AbsoluteUri, mode], out var defaults) &&
                defaults.Contract == ProductContract.ArticleFields && defaults.Browser == (mode == "rendered"));
            Pass(mode + " CLI keeps ArticleFields default without key lookup");
            Require(LiveOptions.TryParse(["--live", Target.AbsoluteUri, mode, "--contract", "single-product-offer-jsonld"], out var selected) &&
                selected.Contract == Contract && selected.Browser == (mode == "rendered"));
            Pass(mode + " CLI selects explicit JSON-LD contract without key lookup");
        }
        Require(LiveOptions.TryParse(["--live", Target.AbsoluteUri, "raw", "--contract", "article-fields"], out var explicitArticle) &&
            explicitArticle.Contract == ProductContract.ArticleFields);
        Pass("CLI accepts explicit ArticleFields selector");
        foreach (var pair in new[] {
            ("unknown contract", new[] { "--live", Target.AbsoluteUri, "rendered", "--contract", "unknown" }),
            ("wrong option", new[] { "--live", Target.AbsoluteUri, "rendered", "--other", "article-fields" }),
            ("HTTP target", new[] { "--live", "http://example.test/", "raw" }),
            ("userinfo", new[] { "--live", "https://user:pass@example.test/", "raw" }),
            ("fragment", new[] { "--live", Target.AbsoluteUri + "#fragment", "raw" }),
            ("unknown mode", new[] { "--live", Target.AbsoluteUri, "unknown" }),
            ("incomplete args", new[] { "--live" }) })
        {
            Require(!LiveOptions.TryParse(pair.Item2, out _)); Pass(pair.Item1 + " CLI input stops before key lookup");
        }
        foreach (bool browser in new[] { false, true })
        {
            var handler = new FakeHandler(request => {
                Equal(request.Method, HttpMethod.Get);
                var query = request.RequestUri!.Query.TrimStart('?').Split('&').Select(p => p.Split('=', 2))
                    .ToDictionary(p => Uri.UnescapeDataString(p[0]), p => Uri.UnescapeDataString(p[1]));
                Equal(query.Count, 6); Equal(query["url"], Target.AbsoluteUri); Equal(query["browser"], browser ? "true" : "false");
                Equal(query["timeout"], "30"); Equal(query["proxy_type"], "datacenter"); Equal(query["proxy_country"], "us");
                Equal(query["return_page_source"], "false"); Equal(request.Headers.GetValues("x-api-key").Single(), FakeKey);
                Require(!request.RequestUri.AbsoluteUri.Contains(FakeKey));
                return Response(browser ? rendered : source, browser ? "10" : "1");
            });
            var acquired = await Client(handler).FetchAsync(Target, browser, CancellationToken.None, maxAttempts: 1, contract: Contract);
            Equal(acquired.Product, Oracle); Equal(acquired.Credits, browser ? 10 : 1); Equal(acquired.Attempts, 1); Equal(handler.Calls, 1);
            Records.Add(new { mode = browser ? "rendered" : "raw", sku = acquired.Product.Sku, title = acquired.Product.Title,
                price = acquired.Product.Price, currency = acquired.Product.Currency, credits = acquired.Credits, attempts = acquired.Attempts });
            Pass((browser ? "rendered" : "raw") + " native FetchAsync fake has explicit request shape and literal record");
            Console.WriteLine($"SIMULATED JSON-LD {(browser ? "rendered" : "raw")}: SYNTH-000 | Synthetic product 000 | 12.34 | USD; mock credits={acquired.Credits}");
        }
        foreach (var failure in new[] { "missing-receipt", "malformed-receipt", "duplicate-receipt", "target403", "missing-target", "non-HTML-type", "invalid-type", "duplicate-type", "malformed-native", "api403", "api503" })
        {
            var handler = new FakeHandler(_ => {
                var response = Response(failure == "malformed-native" ? Html("{bad") : rendered,
                    failure == "missing-receipt" ? null : failure == "malformed-receipt" ? "bad" : "10");
                if (failure == "duplicate-receipt") response.Headers.Add("Ant-credits-cost", "10");
                if (failure is "target403" or "missing-target") {
                    response.Headers.Remove("Ant-page-status-code");
                    if (failure == "target403") response.Headers.Add("Ant-page-status-code", "403");
                }
                if (failure is "non-HTML-type" or "invalid-type") {
                    response.Headers.Remove("Ant-original-header-content-type");
                    response.Headers.Add("Ant-original-header-content-type", failure == "non-HTML-type" ? "application/json" : "bad media type");
                }
                if (failure == "duplicate-type") response.Headers.Add("Ant-original-header-content-type", "text/html");
                if (failure is "api403" or "api503") response.StatusCode = failure == "api403" ? HttpStatusCode.Forbidden : HttpStatusCode.ServiceUnavailable;
                return response;
            });
            try { await Client(handler).FetchAsync(Target, true, CancellationToken.None, maxAttempts: 1, contract: Contract); }
            catch (Exception error) when (error is ContentFailure or ApiFailure) {
                Equal(handler.Calls, 1); Require(!error.ToString().Contains(FakeKey));
                if (failure == "missing-receipt") Require(error.Message.Contains("unknown"));
                Pass(failure + " native acquisition stops after one fake attempt"); continue;
            }
            throw new Exception("Expected native acquisition failure");
        }
        var absentType = new FakeHandler(_ => { var response = Response(rendered); response.Headers.Remove("Ant-original-header-content-type"); return response; });
        Equal((await Client(absentType).FetchAsync(Target, true, CancellationToken.None, maxAttempts: 1, contract: Contract)).Product, Oracle);
        Equal(absentType.Calls, 1); Pass("absent declared type still requires native HTML and schema");
        using (var cancelled = new CancellationTokenSource()) {
            cancelled.Cancel(); var handler = new FakeHandler(_ => Response(rendered));
            bool stopped = false;
            try { await Client(handler).FetchAsync(Target, true, cancelled.Token, maxAttempts: 1, contract: Contract); }
            catch (OperationCanceledException) { stopped = true; }
            Require(stopped); Equal(handler.Calls, 0); Pass("native cancellation before send makes zero attempts");
        }
        Require(ManagedClient.ParseProduct(Html(valid.Replace("12.34", "12.35")), Contract) != Oracle);
        Require(ManagedClient.ParseProduct(Html(valid.Replace("SYNTH-000", "OTHER")), Contract) != Oracle);
        Pass("native literal oracle distinguishes valid-shaped wrong price and SKU");
        using var oracle = JsonDocument.Parse(File.ReadAllText("live-captures/product-jsonld/oracle.json"));
        Equal(oracle.RootElement.GetProperty("sku").GetString(), Oracle.Sku); Equal(oracle.RootElement.GetProperty("title").GetString(), Oracle.Title);
        Equal(oracle.RootElement.GetProperty("price").GetDecimal(), Oracle.Price); Equal(oracle.RootElement.GetProperty("currency").GetString(), Oracle.Currency);
        Pass("committed native oracle agrees with independent literals");
        Directory.CreateDirectory("actual_output");
        File.WriteAllText("actual_output/jsonld-results.json", JsonSerializer.Serialize(new { scope = "offline-owned-jsonld", cases = Passed.Count, records = Records }, new JsonSerializerOptions { WriteIndented = true }) + "\n");
        Console.WriteLine($"PASS {Passed.Count}/{Passed.Count} native JSON-LD and CLI offline cases; live API calls=0");
    }
    private static string Script(string json) => "<script type='application/ld+json'>" + json + "</script>";
    private static string Html(string json) => "<html><body>" + Script(json) + "</body></html>";
    private static void Reject(string name, string html, ProductContract contract = Contract)
    {
        try { ManagedClient.ParseProduct(html, contract); }
        catch (ContentFailure) { Pass(name); return; }
        throw new Exception("Expected explicit contract rejection");
    }
    private static HttpResponseMessage Response(string body, string? receipt = "10")
    {
        var response = new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent(body, Encoding.UTF8) };
        response.Content.Headers.ContentType = null;
        response.Headers.Add("Ant-page-status-code", "200"); response.Headers.Add("Ant-original-header-content-type", "text/html; charset=utf-8");
        if (receipt is not null) response.Headers.Add("Ant-credits-cost", receipt); return response;
    }
    private static ManagedClient Client(FakeHandler handler) => new(new HttpClient(handler), FakeKey);
    private static void Pass(string name) { Passed.Add(name); Console.WriteLine("PASS " + name); }
    private static void Require(bool condition) { if (!condition) throw new Exception("Native offline assertion failed"); }
    private static void Equal<T>(T actual, T expected) => Require(EqualityComparer<T>.Default.Equals(actual, expected));
    private sealed class FakeHandler(Func<HttpRequestMessage, HttpResponseMessage> respond) : HttpMessageHandler
    {
        public int Calls { get; private set; }
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken token)
        { token.ThrowIfCancellationRequested(); Calls++; return Task.FromResult(respond(request)); }
    }
}
