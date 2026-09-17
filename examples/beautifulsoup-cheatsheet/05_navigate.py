from bs4 import BeautifulSoup
from _common import PAGE
soup = BeautifulSoup(PAGE, "html.parser")
price = soup.find("p", class_="price")
print(price.parent.name, price.parent["data-sku"], [p.name for p in price.parents])
card = soup.find("div", class_="product")
print([type(c).__name__ for c in card.contents][:4])                    # whitespace strings are children too
print([c.name for c in card.children if c.name])                        # tags only
print(sum(1 for _ in card.descendants), len(card.find_all(True)))
print(repr(price.next_sibling))                                         # the newline, not the next tag
print(price.find_next_sibling().name, price.find_next_sibling("ul")["class"])
print(price.find_previous_sibling("h2").a.string)
print(price.find_parent("section")["id"], card.find_next_sibling("div")["data-sku"])
print(soup.find("th").next_element, soup.find("tbody").find_next("td").string)
