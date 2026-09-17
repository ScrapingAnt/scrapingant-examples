import requests
from bs4 import BeautifulSoup
from _common import PAGE, show, warn_to_stdout
warn_to_stdout()

soup = BeautifulSoup(PAGE, "html.parser")                 # from a str
print(soup.title.string, "|", soup.h1.get_text(" ", strip=True))
with open("fixtures/page.html", "rb") as f:               # from a file object (bytes: bs4 detects the encoding)
    soup = BeautifulSoup(f, "lxml")
print(soup.original_encoding, soup.title.string)

r = requests.get("https://scrapingant.github.io/scrapingant-examples/fixtures/dynamic-delayed.html", timeout=30)
soup = BeautifulSoup(r.content, "html.parser")            # bytes from a response; not r.text
print(r.status_code, soup.original_encoding, soup.title.string)

latin1 = "<p>Gr\u00fc\u00dfe aus M\u00fcnchen</p>".encode("latin-1")
print(BeautifulSoup(latin1, "html.parser").p.string)                                   # guessed: wrong or right by luck
print(BeautifulSoup(latin1, "html.parser", from_encoding="latin-1").p.string)         # told
show("from_encoding on a str", lambda: BeautifulSoup("<p>x</p>", "html.parser", from_encoding="latin-1").p.string)
show('BeautifulSoup("fixtures/page.html")  # a filename is not markup', lambda: BeautifulSoup("fixtures/page.html", "html.parser").get_text())
