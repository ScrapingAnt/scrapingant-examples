from bs4 import BeautifulSoup
from _common import PAGE
soup = BeautifulSoup(PAGE, "html.parser")
h2 = soup.find("div", attrs={"data-sku": "A300"}).h2
print(str(h2))                                           # minimal formatter: & < > escaped
print(h2.decode(formatter="html"))                       # named entities
print(h2.decode(formatter=None))                         # no escaping at all
print(h2.encode("utf-8"))
print(h2.prettify(), end="")
print(soup.find("nav").prettify())
soup.find("a", class_="active")["checked"] = True         # bool on a parsed tag
soup.find("a", href="/")["hidden"] = False
print(str(soup.nav), type(soup.nav.a.attrs).__name__)
box = soup.new_tag("input", attrs={"type": "checkbox"}); box["checked"] = True; box["disabled"] = False   # bool on a new tag
print(str(box), type(box.attrs).__name__)
