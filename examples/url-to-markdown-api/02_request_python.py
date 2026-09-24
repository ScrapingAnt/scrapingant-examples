"""The same request from Python: status, cost and page-status headers, the two JSON keys, the start of the Markdown."""
import json
import requests
from _common import FIXTURE, KEY, require_key

require_key()
r = requests.get(
    "https://api.scrapingant.com/v2/markdown",
    params={"url": FIXTURE},
    headers={"x-api-key": KEY},
    timeout=120,
)
print("status:", r.status_code, "| Ant-credits-cost:", r.headers.get("Ant-credits-cost"), "| Ant-page-status-code:", r.headers.get("Ant-page-status-code"))
doc = r.json()
print("keys:", sorted(doc))
print("url:", doc["url"])
print("markdown characters:", len(doc["markdown"]))
print("\n".join(doc["markdown"].splitlines()[:12]))
