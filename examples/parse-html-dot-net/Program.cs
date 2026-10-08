using System.Text.Json;

if (args.Contains("--test"))
{
    ParserTests.Run();
    return;
}
var html = await File.ReadAllTextAsync("fixtures/catalog.html");
var pageUrl = new Uri("https://shop.example.test/catalog/index.html");
var records = args.Contains("--hap")
    ? Extractors.WithXPath(html, pageUrl)
    : Extractors.WithCss(html, pageUrl);
Console.WriteLine(JsonSerializer.Serialize(records, new JsonSerializerOptions { WriteIndented = true }));
