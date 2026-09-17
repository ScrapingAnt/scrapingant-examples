"""Fetching the page: pandas' own fetch (urllib) vs storage_options headers vs requests + StringIO, and the BeautifulSoup hand-off."""
from io import StringIO
import pandas as pd
import requests
from bs4 import BeautifulSoup
from _common import URL, show

WIKI = "https://en.wikipedia.org/wiki/List_of_countries_and_dependencies_by_population"
UA = {"User-Agent": "Mozilla/5.0 (compatible; scrapingant-examples/1.0; +https://github.com/ScrapingAnt/scrapingant-examples)"}

show("pd.read_html(WIKI) with pandas' default user agent", lambda: len(pd.read_html(WIKI, match="Population")))
show("pd.read_html(WIKI, storage_options=UA)", lambda: pd.read_html(WIKI, match="Population", storage_options=UA)[0].shape)

r = requests.get(URL, headers=UA, timeout=30)
print("requests.get:", r.status_code, r.headers.get("content-type"))
show("pd.read_html(StringIO(r.text))", lambda: len(pd.read_html(StringIO(r.text))))
show("pd.read_html(r.text)  (old idiom)", lambda: len(pd.read_html(r.text)))

soup = BeautifulSoup(r.text, "lxml")
target = soup.find("table", id="prices")
show("pd.read_html(str(target))  (old idiom)", lambda: pd.read_html(str(target))[0].shape)
show("pd.read_html(StringIO(str(target)))", lambda: pd.read_html(StringIO(str(target)))[0])
show("rows by hand for comparison", lambda: [[c.get_text(strip=True) for c in tr.find_all(["th", "td"])] for tr in target.find_all("tr")][:2])
