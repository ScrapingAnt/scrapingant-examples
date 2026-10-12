using System.Globalization;
using ManagedAcquisition;

if (args.Length == 0 || args.SequenceEqual(new[] { "--offline" }))
{
    await OfflineChecks.RunAsync();
    return 0;
}
if (!LiveOptions.TryParse(args, out var options))
{
    Console.Error.WriteLine("Usage: dotnet run -- --offline | --live HTTPS_URL raw|rendered [--contract article-fields|single-product-offer-jsonld]");
    return 2;
}
// Explicit live opt-in: one GET, no automatic paid retries, never runs from run.sh.
var key = Environment.GetEnvironmentVariable("SCRAPINGANT_API_KEY");
if (string.IsNullOrWhiteSpace(key))
{
    Console.Error.WriteLine("Set SCRAPINGANT_API_KEY locally; no request was sent");
    return 2;
}
try
{
    using var http = new HttpClient(new HttpClientHandler { AllowAutoRedirect = false })
        { Timeout = Timeout.InfiniteTimeSpan };
    using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(95));
    var result = await new ManagedClient(http, key).FetchAsync(options.Target, options.Browser,
        deadline.Token, maxAttempts: 1, contract: options.Contract);
    Console.WriteLine($"LIVE validated record: {result.Product.Sku} | {result.Product.Title} | " +
        $"{result.Product.Price.ToString("0.00", CultureInfo.InvariantCulture)} | {result.Product.Currency}");
    Console.WriteLine($"Credit receipt: {result.Credits.ToString(CultureInfo.InvariantCulture)}");
    return 0;
}
catch (ApiFailure error) { Console.Error.WriteLine(error.Message); }
catch (ContentFailure error) { Console.Error.WriteLine(error.Message); }
catch (OperationCanceledException) { Console.Error.WriteLine("Cancelled; no automatic replacement request"); }
catch (TransportFailure) { Console.Error.WriteLine("Transport failure; no automatic replacement request"); }
catch (ArgumentException) { Console.Error.WriteLine("Invalid input; no request sent"); }
return 1;
