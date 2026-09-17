from bs4 import BeautifulSoup
from _common import PAGE
soup = BeautifulSoup(PAGE, "html.parser")
print(soup.select_one("#products h1").get_text(" ", strip=True))
print([p.string for p in soup.select("div.product p.price")])             # descendant
print([li.string for li in soup.select("div.featured > ul > li")])         # child
print([a["href"] for a in soup.select('a[href^="/p/"]')])                 # attribute prefix
print([a["href"] for a in soup.select('a[rel="nofollow"], a[href^="mailto:"]')])   # union
print(soup.select("div.product:nth-of-type(2) h2 a")[0].string)
print([d["data-sku"] for d in soup.select('div.product:has(p.stock.in)')])   # :has
print([p.string for p in soup.select('p:-soup-contains("Out")')])           # text match (soupsieve extension)
print(soup.select("table#orders tbody tr td:first-child")[0].string, len(soup.select("tbody tr")))
print(soup.select_one("h9"), soup.select("h9"))
# find_all and select say the same thing two ways
print(soup.find_all("p", class_="price") == soup.select("p.price"))
print(soup.find("div", attrs={"data-sku": "A300"}) == soup.select_one('div[data-sku="A300"]'))
