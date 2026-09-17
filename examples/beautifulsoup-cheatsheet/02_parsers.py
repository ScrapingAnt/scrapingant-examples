from bs4 import BeautifulSoup
from bs4.diagnose import diagnose
from _common import BROKEN
for parser in ("html.parser", "lxml", "html5lib"):
    print(f"--- {parser}")
    print(str(BeautifulSoup(BROKEN, parser)))
print("--- diagnose(BROKEN)")
diagnose(BROKEN)
