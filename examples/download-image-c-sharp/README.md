# C# image download: bounded streaming and cleanup

Requires Bash, Python3 and .NET SDK10.0.401 (or10.0.4xx servicing patch allowed by global.json). There are no third-party .NET packages or credentials. The project/lock file pins its target.

```bash
./run.sh
```

The harness runs 15 owned loopback HTTP cases, including PNG/JPEG byte-for-byte SHA256 oracles and negative transport/content/size/timeout/redirect/no-clobber controls. The slow case confirms the server sent the body prefix before cancellation. Default runs compare stable case/byte outcomes to captured results; platform-specific exception names are diagnostics. `./run.sh --capture` explicitly replaces captures; update metadata/hashes after substantive changes.

For a direct application-selected image URL:

```bash
dotnet run -- https://your-controlled-host.example/image.png image.png --max-bytes 5242880 --timeout-ms 15000
```

Replace the placeholder with a real image URL; this command is an invocation template, not a captured external request. HTTP requires explicit `--allow-loopback` and a loopback host, solely for fixture reproduction. Redirects are disabled; select/validate a final URL. Keep normal TLS validation. Existing destination files are preserved. Success publishes the local file after body completion and PNG/JPEG header/signature checks; failure removes the temporary file.

Scope: magic signatures are format filters, not complete image decoding, CRC validation, malware scanning or pixel limits. Local filesystem move is not a crash-durability guarantee. URLs and paths must be trusted/application-selected; this is not an arbitrary user-URL fetch service or an SSRF defense. Tests use loopback HTTP, so they do not measure public-server/TLS/provider behavior. PNG fixture is a synthetic1x1 pixel; JPEG fixture is a local sips conversion of that pixel, not third-party imagery.

Dedicated `dotnet-content-evidence.yml` runs on PR/push/manual/monthly without secrets; generic allowlist does not provision the SDK.
