"""Hidden rows (displayed_only) and nested tables."""
import pandas as pd
from _common import PAGE, show, table

show("hidden: default (displayed_only=True)", lambda: table("hidden"))
show("hidden: displayed_only=False", lambda: table("hidden", displayed_only=False))
show("nested: attrs id=outer", lambda: table("outer"))
show("nested: attrs id=inner", lambda: table("inner"))
show("nested: match='Bin' returns both", lambda: [df.shape for df in pd.read_html(PAGE, match="Bin")])
