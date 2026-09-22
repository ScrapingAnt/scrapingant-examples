"""Derive the dated public-suite table from validated raw observations."""
import json
from pathlib import Path
root = Path(__file__).parent
rows = json.loads((root / "diagnostics/2026-09-22/summary.json").read_text())
print("approach | headless | headed")
for approach in ["chrome-control", "patchright", "python-stealth", "extra-stealth", "rebrowser", "firefox-control", "camoufox"]:
    cells = []
    for mode in ["headless", "headed"]:
        items = [r["browserscan"] for r in rows if r["approach"] == approach and r["mode"] == mode]
        assert len(items) == 2
        assert len({(x["verdict"], tuple(x["flagged"])) for x in items}) == 1
        cells.append(items[0]["verdict"] + (": " + ", ".join(items[0]["flagged"]) if items[0]["flagged"] else ""))
    print(approach + " | " + " | ".join(cells))
