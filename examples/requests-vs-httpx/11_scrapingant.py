"""The same ScrapingAnt API call with both clients. Runs only when SCRAPINGANT_API_KEY is set; skipped (not faked) otherwise."""
import os
import httpx
import requests

KEY = os.environ.get("SCRAPINGANT_API_KEY")
if not KEY:
    print("skipped: SCRAPINGANT_API_KEY is not set"); raise SystemExit(0)
TARGET = "https://scrapingant.github.io/scrapingant-examples/fixtures/dynamic-delayed.html"
API = "https://api.scrapingant.com/v2/general"
params = {"url": TARGET, "browser": "false"}
r = requests.get(API, params=params, headers={"x-api-key": KEY}, timeout=60)
print("requests:", r.status_code, "Ant-credits-cost:", r.headers.get("Ant-credits-cost"), "bytes:", len(r.content))
with httpx.Client(timeout=60) as c:
    r = c.get(API, params=params, headers={"x-api-key": KEY})
    print("httpx:   ", r.status_code, "Ant-credits-cost:", r.headers.get("Ant-credits-cost"), "bytes:", len(r.content), r.http_version)
