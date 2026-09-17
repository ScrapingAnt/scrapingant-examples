"""Dated popularity snapshot: PyPI 30-day downloads and rank (hugovk/top-pypi-packages), Stack Overflow tag counts."""
import datetime as dt, json, sys, urllib.request
TOP = "https://hugovk.github.io/top-pypi-packages/top-pypi-packages-30-days.min.json"
SO = "https://api.stackexchange.com/2.3/tags/{}/info?site=stackoverflow"
pk = ["beautifulsoup4", "soupsieve", "lxml", "html5lib", "requests", "httpx", "playwright", "selenium", "scrapy", "parsel", "pyquery", "selectolax"]
tags = ["beautifulsoup", "selenium", "web-scraping", "scrapy", "lxml", "playwright", "html-parsing"]
d = json.load(urllib.request.urlopen(TOP, timeout=60))
rank = {r["project"]: (i, r["download_count"]) for i, r in enumerate(d["rows"], start=1)}
import gzip
req = urllib.request.Request(SO.format(";".join(tags)), headers={"Accept-Encoding": "gzip"})
raw = urllib.request.urlopen(req, timeout=60).read()
so = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
out = {
    "fetched_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
    "pypi": {"source": TOP, "snapshot_last_update": d["last_update"], "packages_ranked": len(d["rows"]),
             "rows": {p: {"rank": rank[p][0], "downloads_30d": rank[p][1]} if p in rank else None for p in pk}},
    "stackoverflow": {"source": "https://api.stackexchange.com/2.3/tags/{names}/info?site=stackoverflow",
                      "question_count": {t["name"]: t["count"] for t in so["items"]}},
}
json.dump(out, open("expected_output/popularity.json", "w"), indent=1)
bs = out["pypi"]["rows"]["beautifulsoup4"]
print(f"PyPI snapshot {out['pypi']['snapshot_last_update'][:10]}: beautifulsoup4 rank {bs['rank']} of {out['pypi']['packages_ranked']:,}, {bs['downloads_30d']:,} downloads in 30 days")
for p in ("lxml", "playwright", "selenium", "scrapy", "requests"):
    r = out["pypi"]["rows"][p]; print(f"  {p}: rank {r['rank']}, {r['downloads_30d']:,} ({bs['downloads_30d']/r['downloads_30d']:.1f}x)")
print("Stack Overflow questions:", out["stackoverflow"]["question_count"])
