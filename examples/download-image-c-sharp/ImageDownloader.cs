public static class ImageDownloader
{
    public static async Task<long> SaveAsync(HttpClient client, Uri url, string destination,
        long maxBytes, CancellationToken cancellationToken)
    {
        if (maxBytes <= 0) throw new ArgumentOutOfRangeException(nameof(maxBytes));
        using var response = await client.GetAsync(url,
            HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        response.EnsureSuccessStatusCode();
        if (response.StatusCode != System.Net.HttpStatusCode.OK)
            throw new InvalidDataException("Expected a complete HTTP 200 response.");
        var type = response.Content.Headers.ContentType?.MediaType?.ToLowerInvariant();
        if (type is not ("image/png" or "image/jpeg"))
            throw new InvalidDataException("Expected image/png or image/jpeg.");
        if (response.Content.Headers.ContentLength is long size && size > maxBytes)
            throw new InvalidDataException("Declared body exceeds the byte limit.");

        destination = Path.GetFullPath(destination);
        var temporary = destination + "." + Guid.NewGuid().ToString("N") + ".part";
        try
        {
            long total = 0;
            var prefix = new byte[8];
            var prefixLength = 0;
            await using (var input = await response.Content.ReadAsStreamAsync(cancellationToken))
            await using (var output = new FileStream(temporary, FileMode.CreateNew,
                FileAccess.Write, FileShare.None, 16384, FileOptions.Asynchronous))
            {
                var buffer = new byte[16384];
                int read;
                while ((read = await input.ReadAsync(buffer, cancellationToken)) != 0)
                {
                    if (read > maxBytes - total)
                        throw new InvalidDataException("Received body exceeds the byte limit.");
                    var take = Math.Min(read, prefix.Length - prefixLength);
                    buffer.AsSpan(0, take).CopyTo(prefix.AsSpan(prefixLength));
                    prefixLength += take;
                    await output.WriteAsync(buffer.AsMemory(0, read), cancellationToken);
                    total += read;
                }
            }
            byte[] signature = type == "image/png"
                ? [137, 80, 78, 71, 13, 10, 26, 10] : [255, 216, 255];
            if (prefixLength < signature.Length ||
                !prefix.AsSpan(0, signature.Length).SequenceEqual(signature))
                throw new InvalidDataException("Body signature does not match the declared image type.");
            cancellationToken.ThrowIfCancellationRequested();
            // Same-directory move; fail instead of overwriting an existing destination.
            File.Move(temporary, destination, overwrite: false);
            return total;
        }
        finally
        {
            if (File.Exists(temporary)) File.Delete(temporary);
        }
    }
}
