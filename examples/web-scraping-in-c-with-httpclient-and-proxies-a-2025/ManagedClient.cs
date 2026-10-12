using System.Globalization;
using System.Net;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using HtmlAgilityPack;

namespace ManagedAcquisition;

public sealed record Product(string Sku, string Title, decimal Price, string Currency);
public sealed record Acquisition(Product Product, int Credits, int Attempts);
public enum ProductContract { ArticleFields, SingleProductOfferJsonLd }
public sealed class ContentFailure(string message) : Exception(message);
public sealed class ApiFailure(int status, string category) : Exception($"API HTTP {status}: {category}")
{
    public int Status { get; } = status;
    public string Category { get; } = category;
}
public sealed class TransportFailure() : Exception("Transport failure after bounded attempts");

public sealed class ManagedClient(
    HttpClient http,
    string apiKey,
    Func<TimeSpan, CancellationToken, Task>? delay = null)
{
    private const int MaxCharacters = 1_048_576;
    private readonly Func<TimeSpan, CancellationToken, Task> pause = delay ?? Task.Delay;

    public static Uri BuildUri(Uri target, bool browser)
    {
        if (!target.IsAbsoluteUri || target.Scheme != Uri.UriSchemeHttps ||
            target.UserInfo.Length != 0 || target.Fragment.Length != 0)
            throw new ArgumentException("Use an absolute HTTPS target without user info or fragment");
        var query = new Dictionary<string, string>
        {
            ["url"] = target.AbsoluteUri,
            ["browser"] = browser ? "true" : "false",
            ["timeout"] = "30",
            ["proxy_type"] = "datacenter",
            ["proxy_country"] = "us",
            ["return_page_source"] = "false"
        };
        return new Uri("https://api.scrapingant.com/v2/general?" + string.Join("&",
            query.Select(p => $"{Uri.EscapeDataString(p.Key)}={Uri.EscapeDataString(p.Value)}")));
    }

    // GET only. Cancellation is never retried. The caller owns the overall deadline.
    public async Task<Acquisition> FetchAsync(Uri target, bool browser,
        CancellationToken cancellationToken, int maxAttempts = 3,
        ProductContract contract = ProductContract.ArticleFields)
    {
        if (maxAttempts is < 1 or > 3) throw new ArgumentOutOfRangeException(nameof(maxAttempts));
        if (string.IsNullOrWhiteSpace(apiKey)) throw new ArgumentException("An API key is required");
        var uri = BuildUri(target, browser);
        for (var attempt = 1; attempt <= maxAttempts; attempt++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            try
            {
                using var request = new HttpRequestMessage(HttpMethod.Get, uri);
                request.Headers.Add("x-api-key", apiKey);
                using var response = await http.SendAsync(request,
                    HttpCompletionOption.ResponseHeadersRead, cancellationToken);
                var html = await ReadBoundedAsync(response.Content, cancellationToken);
                var status = (int)response.StatusCode;
                if (!response.IsSuccessStatusCode)
                {
                    if (IsTransient(status) && attempt < maxAttempts)
                    {
                        await pause(TimeSpan.FromSeconds(attempt), cancellationToken);
                        continue;
                    }
                    throw new ApiFailure(status, ClassifyError(status, html));
                }

                // The outer API status and target status are different layers.
                var targetStatuses = response.Headers.TryGetValues("Ant-page-status-code", out var statusValues)
                    ? statusValues.ToArray() : [];
                if (targetStatuses.Length != 1 || !int.TryParse(targetStatuses[0], out var targetStatus) ||
                    targetStatus is < 200 or > 299)
                    throw new ContentFailure("Target status is missing, invalid or unsuccessful");
                var originalTypes = response.Headers.TryGetValues("Ant-original-header-content-type", out var typeValues)
                    ? typeValues.ToArray() : [];
                if (originalTypes.Length > 1) throw new ContentFailure("Ambiguous target content type");
                var contentType = originalTypes.SingleOrDefault() ?? response.Content.Headers.ContentType?.ToString();
                if (contentType is not null &&
                    (!System.Net.Http.Headers.MediaTypeHeaderValue.TryParse(contentType, out var declared) ||
                     !(string.Equals(declared.MediaType, "text/html", StringComparison.OrdinalIgnoreCase) ||
                       string.Equals(declared.MediaType, "application/xhtml+xml", StringComparison.OrdinalIgnoreCase))))
                    throw new ContentFailure("Declared content type is not HTML");
                // General responses can omit the outer type. The final HTML/schema guard still applies.
                var product = ParseProduct(html, contract);
                var values = response.Headers.TryGetValues("Ant-credits-cost", out var receipts)
                    ? receipts.ToArray() : [];
                if (values.Length != 1 || !int.TryParse(values[0], NumberStyles.None,
                    CultureInfo.InvariantCulture, out var credits) || credits < 0)
                    throw new ContentFailure("Credit receipt is missing or invalid; cost is unknown");
                return new Acquisition(product, credits, attempt);
            }
            catch (Exception error) when (error is HttpRequestException or IOException)
            {
                if (attempt == maxAttempts) throw new TransportFailure();
                await pause(TimeSpan.FromSeconds(attempt), cancellationToken);
            }
        }
        throw new InvalidOperationException("Unreachable retry state");
    }

    private static bool IsTransient(int status) => status is 500 or 502 or 503 or 504;

    // Never put raw response bodies, key headers, target URLs or transport messages in diagnostics.
    private static string ClassifyError(int status, string body)
    {
        string detail = "";
        try
        {
            using var doc = JsonDocument.Parse(body);
            if (doc.RootElement.ValueKind == JsonValueKind.Object &&
                doc.RootElement.TryGetProperty("detail", out var value) && value.ValueKind == JsonValueKind.String)
                detail = value.GetString() ?? "";
        }
        catch (JsonException) { }
        return status switch
        {
            403 when detail.Contains("Requests quota limit reached", StringComparison.Ordinal) => "quota; pause and check allowance",
            403 when detail.Contains("Access denied from this IP", StringComparison.Ordinal) => "IP access; check whitelist",
            403 when detail.Contains("API token is wrong", StringComparison.Ordinal) => "authentication; check key locally",
            403 => "access; inspect detail privately",
            409 => "concurrency; queue requests",
            400 or 405 or 422 => "input; correct request before retrying",
            429 => "rate limit; respect server schedule",
            _ => "failure; inspect detail privately"
        };
    }

    private static async Task<string> ReadBoundedAsync(HttpContent content, CancellationToken token)
    {
        using var stream = await content.ReadAsStreamAsync(token);
        using var reader = new StreamReader(stream, Encoding.UTF8, detectEncodingFromByteOrderMarks: true);
        var buffer = new char[4096];
        var text = new StringBuilder();
        int read;
        while ((read = await reader.ReadAsync(buffer.AsMemory(), token)) > 0)
        {
            if (text.Length + read > MaxCharacters) throw new ContentFailure("Response exceeds character limit");
            text.Append(buffer, 0, read);
        }
        return text.ToString();
    }

    public static Product ParseProduct(string html, ProductContract contract = ProductContract.ArticleFields)
    {
        if (!html.Contains("<html", StringComparison.OrdinalIgnoreCase))
            throw new ContentFailure("Expected an HTML document");
        var document = new HtmlDocument();
        document.LoadHtml(html);
        if (contract == ProductContract.SingleProductOfferJsonLd) return ParseSingleProductOfferJsonLd(document);
        if (contract != ProductContract.ArticleFields) throw new ContentFailure("Unsupported product contract");
        var products = document.DocumentNode.SelectNodes("//article[@data-sku]");
        if (products is null || products.Count != 1)
            throw new ContentFailure("Expected exactly one product");
        var node = products[0];
        string Text(string xpath) => HtmlEntity.DeEntitize(node.SelectSingleNode(xpath)?.InnerText ?? "").Trim();
        var sku = node.GetAttributeValue("data-sku", "").Trim();
        var title = Text(".//h1");
        var priceText = Text(".//*[@class='price']");
        var currency = node.GetAttributeValue("data-currency", "");
        if (sku.Length == 0 || title.Length == 0 || currency.Length != 3 || !Regex.IsMatch(currency, "^[A-Z]{3}$") ||
            !decimal.TryParse(priceText, NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture, out var price) ||
            price < 0)
            throw new ContentFailure("Missing or invalid required product fields");
        return new Product(sku, title, price, currency);
    }

    // Explicit fixture contract: one Product object and one Offer object, with string values.
    // No automatic fallback, @graph/list support, external context lookup or HTML transformation.
    private static Product ParseSingleProductOfferJsonLd(HtmlDocument document)
    {
        var scripts = document.DocumentNode.SelectNodes("//script[@type='application/ld+json']");
        if (scripts is null || scripts.Count != 1)
            throw new ContentFailure("Expected exactly one product JSON-LD script");
        try
        {
            using var json = JsonDocument.Parse(scripts[0].InnerText);
            var product = json.RootElement;
            static string Text(JsonElement node, string name) =>
                node.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.String
                    ? value.GetString() ?? "" : "";
            static bool UniqueNames(JsonElement node) => node.EnumerateObject().Select(p => p.Name)
                .Distinct(StringComparer.Ordinal).Count() == node.EnumerateObject().Count();
            if (product.ValueKind != JsonValueKind.Object ||
                !UniqueNames(product) || product.TryGetProperty("@graph", out _) ||
                Text(product, "@context") != "https://schema.org" || Text(product, "@type") != "Product" ||
                !product.TryGetProperty("offers", out var offer) || offer.ValueKind != JsonValueKind.Object ||
                !UniqueNames(offer) || Text(offer, "@type") != "Offer")
                throw new ContentFailure("Expected the single Product and Offer JSON-LD contract");
            var sku = Text(product, "sku").Trim();
            var title = Text(product, "name").Trim();
            var currency = Text(offer, "priceCurrency");
            if (sku.Length == 0 || title.Length == 0 || currency.Length != 3 || !Regex.IsMatch(currency, "^[A-Z]{3}$") ||
                !decimal.TryParse(Text(offer, "price"), NumberStyles.AllowDecimalPoint,
                    CultureInfo.InvariantCulture, out var price) || price < 0)
                throw new ContentFailure("Missing or invalid required JSON-LD product fields");
            return new Product(sku, title, price, currency);
        }
        catch (JsonException) { throw new ContentFailure("Malformed product JSON-LD"); }
    }
}
