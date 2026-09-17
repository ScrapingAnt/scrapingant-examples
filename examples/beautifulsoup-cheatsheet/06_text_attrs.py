from bs4 import BeautifulSoup
from _common import PAGE, show
soup = BeautifulSoup(PAGE, "html.parser")
h1 = soup.h1
print(repr(h1.string), "|", repr(h1.get_text()), "|", h1.get_text(" ", strip=True))   # .string is None with several children
print(soup.find("p", class_="price").string, soup.find("p", class_="price").text)
print(list(soup.find("div", class_="product").stripped_strings))
print(soup.nav.get_text("|", strip=True))
a = soup.find("a", class_="active")
print(a["href"], a.get("href"), a.get("target"), a.get("target", "_self"), a.has_attr("rel"))
show("a['target']", lambda: a["target"])
print(a["class"], soup.find("div", class_="featured")["class"])              # class is a list
print(soup.find("div", class_="featured").attrs)
print(soup.find("a", href="https://example.com/help")["rel"])              # rel is multi-valued too
print(soup.find("h2").a.string, soup.find("h2").get_text())
