import xmltodict, untangle, pandas as pd
from bs4 import BeautifulSoup

d = xmltodict.parse(open("fixtures/books.xml", "rb").read())
print("xmltodict keys:", list(d["catalog"].keys()), "first title:", d["catalog"]["book"][0]["title"])
print("xmltodict price:", d["catalog"]["book"][0]["price"])
print("xmltodict unparse:", xmltodict.unparse({"root": {"item": ["a", "b"]}}, pretty=False))
print("xmltodict sitemap:", [u["loc"] for u in xmltodict.parse(open("fixtures/sitemap.xml", "rb").read())["urlset"]["url"]])

o = untangle.parse("fixtures/books.xml")
print("untangle:", o.catalog["updated"], o.catalog.book[0]["id"], o.catalog.book[0].title.cdata, o.catalog.book[1].price["currency"])

soup = BeautifulSoup(open("fixtures/sitemap.xml", "rb").read(), features="xml")
print("bs4 xml:", [loc.text for loc in soup.find_all("loc")], "alternates:", [l["href"] for l in soup.find_all("link")])
print("bs4 recover broken:", BeautifulSoup(open("fixtures/broken.xml", "rb").read(), features="xml").find("title").text.strip())

df = pd.read_xml("fixtures/books.xml", xpath="//book")
print("pandas columns:", list(df.columns)); print(df[["id", "lang", "title", "price"]].to_string(index=False))
print("pandas sitemap:", pd.read_xml("fixtures/sitemap.xml", xpath="//sm:url", namespaces={"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"})["loc"].tolist())
