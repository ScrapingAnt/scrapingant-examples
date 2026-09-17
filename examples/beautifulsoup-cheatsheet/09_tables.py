from io import StringIO
import pandas as pd
from bs4 import BeautifulSoup
from _common import PAGE, show, warn_to_stdout
warn_to_stdout()
soup = BeautifulSoup(PAGE, "html.parser")
table = soup.find("table", id="orders")
rows = [[td.get_text(strip=True) for td in tr.find_all(["th", "td"])] for tr in table.find_all("tr")]
print(rows)
records = [dict(zip(rows[0], r)) for r in rows[1:]]
print(records[0])
df = pd.read_html(StringIO(str(table)))[0]
print(df.dtypes.to_dict()); print(df.to_string(index=False))
show("pd.read_html(str(table))  # the old spelling", lambda: len(pd.read_html(str(table))[0]))   # pandas 3 treats a str as a path
