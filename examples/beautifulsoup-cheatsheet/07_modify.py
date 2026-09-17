from bs4 import BeautifulSoup
from _common import PAGE
soup = BeautifulSoup(PAGE, "html.parser")
card = soup.find("div", attrs={"data-sku": "A200"})
card.find("p", class_="stock").string = "Back in stock"
card["class"].append("restocked"); card["data-updated"] = "2026-09-17"
new = soup.new_tag("p", attrs={"class": "note"}); new.string = "Ships in 2 days"
card.append(new)
card.insert(0, soup.new_tag("span", attrs={"class": "badge"}))
card.h2.insert_before(soup.new_string("[NEW] "))
print(card.prettify())
removed = soup.find("script").decompose()                     # gone, returns None
taken = soup.find("footer").extract()                          # removed and returned
print(removed, taken.name, soup.find("footer"))
soup.find("h1").small.unwrap()                                 # keep the text, drop the tag
soup.find("nav").wrap(soup.new_tag("header"))
print(soup.find("h1"), soup.find("header").nav["id"])
soup.find("p", class_="price").replace_with(soup.new_tag("s"))
soup.find("ul", class_="tags").clear()
print(soup.find("div", class_="featured").prettify())
