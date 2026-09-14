"""ScrapingAnt Web Scraping API: rendering happens in the cloud, one HTTP call per page.

Uses `requests` directly so the `Ant-credits-cost` response header is visible.
The official client (scrapingant-client) wraps the same endpoint; see the end of the file.
Fixtures must be reachable from the internet, so the public GitHub Pages copies are used.
"""
import os

import requests
from bs4 import BeautifulSoup

from _fixtures import PUBLIC

API_KEY = os.environ["SCRAPINGANT_API_KEY"]
ENDPOINT = "https://api.scrapingant.com/v2/general"


def fetch(url: str, **params) -> tuple[str, str]:
    # The key goes in a header, not the query string, so it does not end up in URL logs.
    r = requests.get(ENDPOINT, params={"url": url, **params}, headers={"x-api-key": API_KEY}, timeout=120)
    r.raise_for_status()
    return r.text, r.headers.get("Ant-credits-cost", "?")


# 1. Default request: headless browser with JavaScript rendering, datacenter proxy.
html, cost = fetch(PUBLIC["domcontentloaded"])
soup = BeautifulSoup(html, "html.parser")
print(f"domcontentloaded (browser=true): {soup.find(id='test').get_text()}  [credits: {cost}]")

# 2. Same page without a browser (1 credit instead of 10): JavaScript never runs.
html, cost = fetch(PUBLIC["domcontentloaded"], browser="false")
soup = BeautifulSoup(html, "html.parser")
print(f"domcontentloaded (browser=false): {soup.find(id='test').get_text()}  [credits: {cost}]")

# 3. Delayed content: tell the API which element to wait for before returning.
html, cost = fetch(PUBLIC["delayed"], wait_for_selector="#loaded")
soup = BeautifulSoup(html, "html.parser")
print(f"delayed (wait_for_selector=#loaded): {soup.find(id='test').get_text()}  [credits: {cost}]")

# Equivalent call with the official client (no access to response headers):
from scrapingant_client import ScrapingAntClient  # noqa: E402

client = ScrapingAntClient(token=API_KEY)
result = client.general_request(PUBLIC["delayed"], wait_for_selector="#loaded")
soup = BeautifulSoup(result.content, "html.parser")
print(f"delayed via scrapingant-client: {soup.find(id='test').get_text()}")
