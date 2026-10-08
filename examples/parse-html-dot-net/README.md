# HTML parsing in .NET: CSS and XPath

Requires Bash and .NET SDK 10.0.401 (or a 10.0.4xx servicing patch allowed by global.json). Restore uses public NuGet; the extraction itself is offline and needs no credentials.

```bash
./run.sh
```

`ParserDemo.csproj` pins AngleSharp 1.8.4 and HtmlAgilityPack 1.13.0; packages.lock.json freezes transitive packages. `Program.cs` prints the CSS result; add `--hap` after `dotnet run --` for XPath. Both implementations have the same literal three-record oracle, including a class-token decoy, nested text, entities and absolute/relative URLs. Tests reject missing fields/non-HTTP URL schemes, distinguish no matches from invalid records and prove that the parser does not run the fixture's script. No network loader or JavaScript engine is configured.

Default runs compare both fresh outputs with the captures and leave committed captures unchanged. `./run.sh --capture` explicitly replaces captures after a substantive change; update evidence and hashes as well. 15 assertions in the dated run; no speed or real-site reliability benchmark. Selectors are fixture-specific. `pageUrl` is explicit; `<base href>` is not implemented. HTML parser tree repair can differ on malformed input; identical output here is no universal equivalence claim.

Maintained by the dedicated `dotnet-content-evidence.yml` workflow (PR/push/manual/monthly), without secrets. Not added to the generic Python/browser workflow allowlist, which does not provision the pinned SDK.
