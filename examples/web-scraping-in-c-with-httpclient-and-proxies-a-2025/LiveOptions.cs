using System.Diagnostics.CodeAnalysis;

namespace ManagedAcquisition;

public sealed record LiveOptions(Uri Target, bool Browser, ProductContract Contract)
{
    // Parsing options performs no credential lookup or HTTP request.
    public static bool TryParse(string[] args, [NotNullWhen(true)] out LiveOptions? options)
    {
        options = null;
        if (args.Length is not (3 or 5) || args[0] != "--live" || args[2] is not ("raw" or "rendered"))
            return false;
        var contract = ProductContract.ArticleFields;
        if (args.Length == 5)
        {
            if (args[3] != "--contract") return false;
            contract = args[4] switch
            {
                "article-fields" => ProductContract.ArticleFields,
                "single-product-offer-jsonld" => ProductContract.SingleProductOfferJsonLd,
                _ => (ProductContract)(-1)
            };
            if ((int)contract == -1) return false;
        }
        if (!Uri.TryCreate(args[1], UriKind.Absolute, out var target)) return false;
        try { _ = ManagedClient.BuildUri(target, args[2] == "rendered"); }
        catch (ArgumentException) { return false; }
        options = new(target, args[2] == "rendered", contract);
        return true;
    }
}
