# Python Requests proxy guide: local lab

Evidence for https://scrapingant.com/blog/python-requests-proxy. `lab.py` starts an echo origin on 127.0.0.1:8000, proxy.py proxies on 8899 (Basic auth `lab` / `p@ss#w0rd`), 8901 and 8902, and a SOCKS5 proxy (pproxy, `lab` / `secret`) on 1080. Port 8903 stays closed as a dead proxy. The HTTP proxies add an `X-Lab-Proxy` header to plain-HTTP requests, so the origin's JSON shows which proxy carried each request.

Each file in `cases/` is a snippet from the article. `lab.py` runs them and saves `expected_output/<case>.txt` (stdout, stderr and `exit=`). Case 09 calls the ScrapingAnt proxy mode and runs only when `SCRAPINGANT_API_KEY` is set; it prints country and city, not IPs.

```bash
uv venv .venv && source .venv/bin/activate
uv pip install -r requirements.txt
SCRAPINGANT_API_KEY=... ./run.sh   # or ./run.sh to skip case 09
```

Needs free loopback ports 8000, 8899, 8901, 8902, 1080 and outbound HTTPS for case 05 (example.com) and 09.
