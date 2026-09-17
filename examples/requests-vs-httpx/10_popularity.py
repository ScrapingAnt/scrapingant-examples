"""Dated popularity snapshot: 30-day PyPI downloads (hugovk/top-pypi-packages) for requests, httpx, aiohttp, urllib3, niquests, pycurl."""
import json
import datetime as dt
import httpx

SRC = "https://hugovk.github.io/top-pypi-packages/top-pypi-packages.min.json"
data = httpx.get(SRC, timeout=60, follow_redirects=True).json()
rows = data["rows"]
rank = {r["project"]: (i + 1, r["download_count"]) for i, r in enumerate(rows)}
out = {"source": SRC, "snapshot_last_update": data.get("last_update"), "fetched_at": dt.date.today().isoformat(),
       "total_projects": len(rows), "packages": {}}
for p in ["requests", "httpx", "aiohttp", "urllib3", "httpcore", "niquests", "pycurl", "h2"]:
    if p in rank:
        out["packages"][p] = {"rank": rank[p][0], "downloads_30d": rank[p][1]}
    else:
        out["packages"][p] = {"rank": None, "downloads_30d": None, "note": f"not in top {len(rows)}"}
json.dump(out, open("expected_output/popularity.json", "w"), indent=2)
print(f"30-day PyPI downloads, snapshot {out['snapshot_last_update']} (top {len(rows):,} packages), fetched {out['fetched_at']}")
for p, v in out["packages"].items():
    print(f"{p:<10} rank {str(v['rank']):>6}  downloads {v['downloads_30d'] or 0:>15,}")
