using System.Net;
using AngleSharp.Html.Parser;
using HtmlAgilityPack;

public sealed record Product(string Id, string Title, string Url);

public static class Extractors
{
    public static Product[] WithCss(string html, Uri pageUrl)
    {
        using var document = new HtmlParser().ParseDocument(html);
        return document.QuerySelectorAll("#catalog article.product")
            .Select(card =>
            {
                var link = card.QuerySelector("a.name");
                // DOM TextContent/GetAttribute already contain decoded entities.
                return Create(card.GetAttribute("data-id"), link?.TextContent,
                    link?.GetAttribute("href"), pageUrl);
            }).ToArray();
    }

    public static Product[] WithXPath(string html, Uri pageUrl)
    {
        var document = new HtmlDocument();
        document.LoadHtml(html);
        var cards = document.DocumentNode.SelectNodes(
            "//*[@id='catalog']//article[contains(concat(' ', normalize-space(@class), ' '), ' product ')]");
        if (cards is null) return [];
        return cards.Select(card =>
        {
            var link = card.SelectSingleNode(
                ".//a[contains(concat(' ', normalize-space(@class), ' '), ' name ')]");
            // Decode once for HAP, including attributes; never decode DOM text twice.
            return Create(WebUtility.HtmlDecode(card.GetAttributeValue("data-id", null)),
                WebUtility.HtmlDecode(link?.InnerText),
                WebUtility.HtmlDecode(link?.GetAttributeValue("href", null)), pageUrl);
        }).ToArray();
    }

    private static Product Create(string? id, string? title, string? href, Uri pageUrl)
    {
        if (string.IsNullOrWhiteSpace(id) || string.IsNullOrWhiteSpace(title) ||
            string.IsNullOrWhiteSpace(href))
            throw new InvalidDataException("A product requires data-id, title and href.");
        if (!Uri.TryCreate(pageUrl, href, out var url) ||
            (url.Scheme != Uri.UriSchemeHttp && url.Scheme != Uri.UriSchemeHttps))
            throw new InvalidDataException("Product href must resolve to HTTP or HTTPS.");
        return new Product(id.Trim(), title.Trim(), url.AbsoluteUri);
    }
}
