# IP restrictions guide: local rate-limit lab

Evidence for https://scrapingant.com/blog/ip-restriction-protection. `lab.py` starts an origin on 127.0.0.1:8000 that allows 5 requests per 10-second window per client, answers 429 with `Retry-After` over the limit, and bans a client (403) after more than 3 refused requests in a row. Two proxy.py proxies (8901, 8902) stamp requests with `X-Lab-Proxy`; on loopback the origin cannot see real exit IPs, so it treats that header as the client identity. This simulates two exit IPs and is disclosed in the article.

Each file in `cases/` is a snippet from the article; outputs go to `expected_output/<case>.txt`. Case 05 calls the ScrapingAnt API and runs only with `SCRAPINGANT_API_KEY` (prints country and region, not IPs).

```bash
uv venv .venv && source .venv/bin/activate && uv pip install -r requirements.txt
SCRAPINGANT_API_KEY=... ./run.sh
```
