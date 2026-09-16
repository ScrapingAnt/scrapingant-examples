# How to Ignore SSL Certificate Errors in Python Requests (and when not to)

Evidence packet for https://scrapingant.com/blog/requests-ignore-ssl

## What this demonstrates
Every recipe in the article, run against a local HTTPS server that presents a self-signed certificate (issued for `localhost` only), plus one request to a public page with a valid certificate. The output files hold the exact exception text, the `InsecureRequestWarning` line, and the negative cases that show which popular recipes do not work in current `requests`: `REQUESTS_CA_BUNDLE=""`, `verify=<SSLContext>`, `PYTHONHTTPSVERIFY=0`, a `CERT_NONE` context mounted through an adapter, and a per-request `verify=True` overriding `Session.verify=False`.

## Run
```bash
pip install -r requirements.txt
./run.sh
```
Requires Python 3.12 and the `openssl` command (it generates `certs/localhost.pem` on first run). No API key.

## Files
- `run.sh` — generates the certificate, starts `server.py` on `https://localhost:8443`, runs `NN_*.py`, writes `expected_output/*.txt`, checks the results
- `server.py` — `http.server` wrapped in an `ssl.SSLContext` serving `fixtures/`
- `_common.py` — prints results and exceptions in one line each
- `01`–`12` — one script per recipe (`env_check.py` is the one-request helper for the shell cases) (see `evidence.yaml: claims`)
- `expected_output/` — captured output from the last recorded run (`evidence.yaml: tested_at`)

## Limitations
- The server is local; a corporate TLS-intercepting proxy is described in the article, not run.
- macOS `Install Certificates.command` and `truststore` are documented, not run (they change the machine's trust store).
