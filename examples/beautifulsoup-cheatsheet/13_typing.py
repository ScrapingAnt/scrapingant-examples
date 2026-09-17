"""What the 4.14+ overloads give a type checker: run through mypy by run.sh."""
from bs4 import BeautifulSoup, Tag, NavigableString

with open("fixtures/page.html", "rb") as f:
    soup = BeautifulSoup(f, "html.parser")
h2: Tag | None = soup.find("h2")                              # find(name) is typed Tag | None
first_stock: NavigableString | None = soup.find(string="In stock")   # find(string=...) is NavigableString | None
if h2 is not None:
    print(h2.name, h2.get_text())
if first_stock is not None:
    print(first_stock.parent.name if first_stock.parent else None)
prices: list[Tag] = list(soup.find_all("p", class_="price"))   # find_all(name) elements are Tag
print(len(prices))
