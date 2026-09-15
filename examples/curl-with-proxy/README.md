# How to use cURL with a proxy

Evidence packet for https://scrapingant.com/blog/curl-with-proxy

## What this demonstrates
Every command in the article, run against proxies that `run.sh` starts on localhost:

| Port | What | Purpose |
|---|---|---|
| 8080 | HTTP proxy with Basic auth (`proxy.py`) | authentication, real `407 Proxy Authentication Required` |
| 8081 | HTTP proxy without auth (`pproxy`) | environment variables, `no_proxy`, precedence |
| 1080 | SOCKS5 proxy with auth (`pproxy`) | `socks5://` vs `socks5h://` name resolution |
| 8000 | local HTTP target (`python -m http.server`) | plain `GET` through a proxy, 407 on an `http://` target |

The HTTPS target is the public fixture at https://scrapingant.github.io/scrapingant-examples/fixtures/dynamic-delayed.html, so `CONNECT` tunnelling is exercised for real.

## Run
```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
./run.sh
```
`run.sh` records one file per case in `expected_output/` (`$ command`, output, exit code) and asserts the expected status codes and exit codes. Verbose (`-v`) transcripts are trimmed to the proxy-related lines and non-loopback IP addresses are masked as `<ip>`, so runs are comparable; a real `-v` prints many more lines. It needs `curl` on `PATH` and outbound HTTPS.

## Diagrams
`diagrams/*.d2` are the sources of the two figures in the article (render with `d2 --layout dagre`).

## Not covered
- A TLS-speaking proxy (`-x https://…`), so `--proxy-cacert` / `--proxy-insecure` are documented from the manual, not run.
- ScrapingAnt's own proxy endpoints (need account credentials); the docs' test command is quoted, not executed.
