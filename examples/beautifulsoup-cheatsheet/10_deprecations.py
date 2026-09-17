import re
from bs4 import BeautifulSoup
from _common import PAGE, warn_to_stdout
warn_to_stdout()
soup = BeautifulSoup(PAGE, "html.parser")
print(len(soup.findAll("p")))                          # camelCase: deprecated in 4.13, warns, removal announced
print(soup.find("h1").getText(" ", strip=True))
print(repr(soup.find("th").nextSibling))
print([p.string for p in soup.find_all("p", text=re.compile("stock"))])   # text= -> string=
print([p.string for p in soup.find_all("p", string=re.compile("stock"))])
