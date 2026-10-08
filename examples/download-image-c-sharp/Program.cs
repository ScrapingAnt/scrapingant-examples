try
{
    if (args.Length < 2)
        throw new ArgumentException("Usage: dotnet run -- <https-url> <destination> [--max-bytes N] [--timeout-ms N]");
    var url = new Uri(args[0]);
    // Explicit opt-in for this repository's local fixture only.
    var localFixture = args.Contains("--allow-loopback") && url.IsLoopback;
    if (url.Scheme != "https" && !(localFixture && url.Scheme == "http"))
        throw new ArgumentException("Use an HTTPS URL; HTTP is only allowed for opted-in loopback fixtures.");
    int Option(string name, int fallback)
    {
        var i = Array.IndexOf(args, name);
        if (i < 0) return fallback;
        if (i + 1 == args.Length) throw new ArgumentException(name + " needs a value.");
        return int.Parse(args[i + 1], System.Globalization.CultureInfo.InvariantCulture);
    }
    var maxBytes = Option("--max-bytes", 5 * 1024 * 1024);
    var timeoutMs = Option("--timeout-ms", 15000);
    if (maxBytes <= 0 || timeoutMs <= 0) throw new ArgumentException("Limits must be positive.");
    using var client = new HttpClient(new SocketsHttpHandler { AllowAutoRedirect = false });
    using var timeout = new CancellationTokenSource(TimeSpan.FromMilliseconds(timeoutMs));
    var bytes = await ImageDownloader.SaveAsync(client, url, args[1], maxBytes, timeout.Token);
    Console.WriteLine($"saved {bytes} bytes");
}
catch (Exception error) when (error is HttpRequestException or IOException or InvalidDataException or
    OperationCanceledException or ArgumentException or FormatException or OverflowException)
{
    Console.Error.WriteLine(error.GetType().Name + ": " + error.Message);
    Environment.ExitCode = 1;
}
