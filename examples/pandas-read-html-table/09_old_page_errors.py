"""The recipes from the 2024 version of this page that no longer run, with their messages."""
import pandas as pd
from _common import PAGE, show, table

df = table("simple")
show("df.append({...}, ignore_index=True)  (removed in pandas 2.0)", lambda: df.append({"Name": "Ken", "Age": 60, "City": "Murray Hill"}, ignore_index=True))
show("pd.concat([df, pd.DataFrame([{...}])])", lambda: pd.concat([df, pd.DataFrame([{"Name": "Ken", "Age": 60, "City": "Murray Hill"}])], ignore_index=True))
show("pd.read_html(PAGE, chunksize=1000)", lambda: pd.read_html(PAGE, chunksize=1000))
show("pd.read_html(PAGE, usecols=[0, 1])", lambda: pd.read_html(PAGE, usecols=[0, 1]))
show("table('simple')[['Name', 'Age']] instead", lambda: table("simple")[["Name", "Age"]])
show("pd.read_html(PAGE, 'Ant Farm')  (match positionally)", lambda: [d.shape for d in pd.read_html(PAGE, "Ant Farm")])
show("table('simple', header=5) (row beyond the table)", lambda: table("simple", header=5))
