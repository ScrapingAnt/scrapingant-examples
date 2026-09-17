"""Picking the table you want: match (text or regex), attrs, index, and what happens when nothing matches."""
import re
import pandas as pd
from _common import PAGE, show

show("match='Ant Farm'", lambda: [df.shape for df in pd.read_html(PAGE, match="Ant Farm")])
show("match='Ant Farm Deluxe'", lambda: [df.shape for df in pd.read_html(PAGE, match="Ant Farm Deluxe")])
show("match=re.compile(r'^Q[1-4]$')", lambda: [df.shape for df in pd.read_html(PAGE, match=re.compile(r"^Q[1-4]$"))])
show("attrs={'id': 'prices'}", lambda: pd.read_html(PAGE, attrs={"id": "prices"})[0])
show("attrs={'class': 'data'}", lambda: [df.shape for df in pd.read_html(PAGE, attrs={"class": "data"})])
show("match='Magnifier', attrs={'class': 'data'}", lambda: [df.shape for df in pd.read_html(PAGE, match="Magnifier", attrs={"class": "data"})])
show("match='no such text'", lambda: pd.read_html(PAGE, match="no such text"))
show("attrs={'id': 'nope'}", lambda: pd.read_html(PAGE, attrs={"id": "nope"}))
show("pd.read_html('fixtures/no-tables.html')", lambda: pd.read_html("fixtures/no-tables.html"))
