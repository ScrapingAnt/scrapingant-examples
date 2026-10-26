# Playwright MCP behind a proxy: local lab

Evidence for https://scrapingant.com/blog/playwright-mcp-server-proxy. `run.sh` starts two proxy.py proxies (8899 with Basic auth `lab` / `p@ss#w0rd`, 8901 without auth) that stamp plain-HTTP requests with `X-Lab-Proxy`. `cases/navigate.mjs` starts Playwright MCP over stdio with the flags under test, calls `browser_navigate` on http://httpbin.org/headers and `browser_evaluate` to read the echoed headers, and prints which proxy (if any) carried the request or the error it got. Environment variables reach the server the way an MCP client's `env` block passes them.

Case 08 talks to the hosted ScrapingAnt MCP server and runs only with `SCRAPINGANT_API_KEY`; it prints the tool list and the country/city of a residential exit, not the IP.

```bash
npm ci && npx playwright install chromium-headless-shell
uv venv .venv && source .venv/bin/activate && uv pip install -r requirements.txt
SCRAPINGANT_API_KEY=... ./run.sh > expected_output/run.txt
```

Needs loopback ports 8899 and 8901 and outbound HTTP to httpbin.org.
