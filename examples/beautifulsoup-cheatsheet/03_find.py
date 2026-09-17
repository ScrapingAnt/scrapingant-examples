import re
from bs4 import BeautifulSoup
from _common import PAGE, show
soup = BeautifulSoup(PAGE, "html.parser")
print(soup.find("h2"))                                            # first match, or None
print([a["href"] for a in soup.find_all("a")])                    # by tag name
print([t.name for t in soup.find_all(["h1", "h2"])])              # list of names
print(len(soup.find_all(True)))                                   # every tag
print([p.string for p in soup.find_all("p", class_="price")])     # class_ (class is a keyword)
print([d["data-sku"] for d in soup.find_all("div", attrs={"data-sku": True})])   # attrs dict; True = present
print([d["data-sku"] for d in soup.find_all("div", class_="featured")])          # matches one of several classes
print(soup.find("div", attrs={"data-sku": "A200"}).h2.a.string)
print([a.string for a in soup.find_all("a", href=re.compile(r"^/p/"))])          # regex on an attribute
print([p.string for p in soup.find_all("p", string=re.compile(r"stock"))])       # string= matches the text
print([li.string for li in soup.find_all("li", limit=2)])
print(len(soup.find_all("li")), len(soup.find("section").find_all("div", recursive=False)))
print([t.name for t in soup.find_all(lambda tag: tag.name == "p" and "in" in tag.get("class", []))])   # a function
show("soup.find('h9')", lambda: soup.find("h9"))
print(soup.find(id="top").name, soup.find(id="missing"))
