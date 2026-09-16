# How to Send POST Requests With Wget

Evidence packet for https://scrapingant.com/blog/wget-post-requests

## What this demonstrates
Every wget command in the article, run against `server.py`, a local HTTP server that echoes the request it received (method, headers, body, parsed form) and provides redirect (301/302/303/307/308), error-body, Basic-auth, cookie-login, flaky-503 and slow endpoints. The outputs show what the tested wget actually does, including the redirect behaviour that differs from the manual's text.

## Run
```bash
./run.sh
```
Needs `wget`, `curl` (one multipart case) and Python 3 for the server. No API key, no network. `run.sh` sets `LC_ALL=C` so wget's messages are in English, and masks dates, the server banner, the user-agent version and multipart boundaries so a run on another machine compares cleanly.

## Files
- `run.sh` — starts the server, records one file per case (command, output, exit code), checks key strings
- `server.py` — the target
- `fixtures/` — `data.json` (JSON body), `form.txt`
- `expected_output/` — captured output from the last recorded run (`evidence.yaml: tested_at`)
- `server.log` — the request sequence the server saw

## Limitations
- One wget version per run; the redirect handling (section 7 of the article) is version-dependent.
- No HTTPS; no ScrapingAnt API call (needs a key).
