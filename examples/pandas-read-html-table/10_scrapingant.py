"""Tables that only exist after JavaScript runs: fetch the rendered HTML through the ScrapingAnt API, then read_html. Skipped without a key."""
import os
from io import StringIO
import pandas as pd
import requests

KEY = os.environ.get("SCRAPINGANT_API_KEY")
if not KEY:
    print("skipped: SCRAPINGANT_API_KEY is not set"); raise SystemExit(0)
TARGET = "https://scrapingant.github.io/scrapingant-examples/fixtures/html-tables.html"
r = requests.get("https://api.scrapingant.com/v2/general", params={"url": TARGET, "browser": "true"}, headers={"x-api-key": KEY}, timeout=90)
print("status:", r.status_code, "Ant-credits-cost:", r.headers.get("Ant-credits-cost"))
tables = pd.read_html(StringIO(r.text), attrs={"id": "prices"})
print(tables[0])
