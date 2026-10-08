using System.Text.Json;

public static class ParserTests
{
    public static void Run()
    {
        var pageUrl = new Uri("https://shop.example.test/catalog/index.html");
        Product[] expected = [
            new("tea", "Tea & biscuits", "https://shop.example.test/items/tea?pack=1&size=2"),
            new("cafe", "Café \"Noir\"", "https://shop.example.test/items/cafe"),
            new("literal", "Literal &lt;tag&gt;", "https://cdn.example.test/items/literal")
        ];
        var count = 0;
        foreach (var (name, parse) in new (string, Func<string, Uri, Product[]>)[] {
            ("css", Extractors.WithCss), ("xpath", Extractors.WithXPath) })
        {
            Equal(expected, parse(File.ReadAllText("fixtures/catalog.html"), pageUrl), name + " literal oracle"); count++;
            Equal([], parse("<main id='catalog'></main>", pageUrl), name + " no matches"); count++;
            Equal([], parse("<main id='catalog'></main><script>document.querySelector('#catalog').innerHTML = \"<article class='product' data-id='js'>injected</article>\";</script>", pageUrl), name + " scripts stay unexecuted"); count++;
            foreach (var (label, body) in new[] {
                ("missing href", "<a class='name'>Title</a>"),
                ("missing title", "<a class='name' href='/item'> </a>"),
                ("wrong scheme", "<a class='name' href='javascript:alert(1)'>Title</a>"),
                ("missing id", "<a class='name' href='/item'>Title</a>") })
            {
                var id = label == "missing id" ? "" : "data-id='one'";
                try { parse($"<main id='catalog'><article class='product' {id}>{body}</article></main>", pageUrl); }
                catch (InvalidDataException) { count++; continue; }
                throw new Exception(name + " accepted " + label);
            }
        }
        // A false oracle must fail, even if a parser returns three plausible records.
        try { Equal(expected, expected.Reverse().ToArray(), "wrong order control"); }
        catch (Exception) { count++; Console.WriteLine($"PASS {count} parser assertions"); return; }
        throw new Exception("Oracle accepted wrong record order");
    }
    private static void Equal(Product[] expected, Product[] actual, string label)
    {
        if (!expected.SequenceEqual(actual))
            throw new Exception(label + "\nactual=" + JsonSerializer.Serialize(actual));
    }
}
