"""Parse the fixtures without a browser. Shows why a plain HTML parser is not enough."""
from bs4 import BeautifulSoup

from _fixtures import LOCAL

for name, path in LOCAL.items():
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    print(f"{name}: {soup.find(id='test').get_text()}")
