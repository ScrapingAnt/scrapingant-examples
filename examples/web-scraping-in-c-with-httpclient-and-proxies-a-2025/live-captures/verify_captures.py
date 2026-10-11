"""Replay saved owned-fixture evidence only; no network or credential access."""
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path


class Markers(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nodes = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "id": dict(attrs).get("id"), "text": ""}
        self.nodes.append(node)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input",
                       "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        for node in self.stack:
            node["text"] += data


root = Path(__file__).resolve().parent
allowed = {"phase", "scope", "mode", "started_utc", "finished_utc", "latency_ms",
           "requests", "outer_status", "target_status", "actual_cost", "original_target_type",
           "outer_type", "body_bytes", "body_sha256", "marker_valid", "accepted", "failure",
           "validates_public_sku_parser", "body_saved"}
oracles = {
    "raw": (1, 752, "d670add5613e47f7e29d08480a1eec2b2fca04e94e18eba4628fe44e9b124e93",
            "Web Scraping is hard"),
    "rendered": (10, 796, "f004947fad2498c56cc12f09d65d2adc9cb68f518e32a18c9aa0e54bba0e56c9",
                 "I ❤️ ScrapingAnt (after 1500 ms)"),
}
for mode, (cost, size, digest, text) in oracles.items():
    receipt = json.loads((root / mode / "receipt.json").read_text(encoding="utf-8"))
    body = (root / mode / "response.html").read_bytes()
    assert set(receipt) == allowed, "Unexpected receipt fields"
    assert len(body) == size == receipt["body_bytes"], "Body size differs"
    assert hashlib.sha256(body).hexdigest() == digest == receipt["body_sha256"], "Body hash differs"
    assert receipt["mode"] == mode and receipt["scope"] == "owned-delayed-marker-only"
    assert receipt["outer_status"] == receipt["target_status"] == 200
    assert receipt["requests"] == 1 and receipt["actual_cost"] == cost
    assert receipt["original_target_type"] == "text/html"
    assert receipt["accepted"] is True and receipt["marker_valid"] is True
    assert receipt["body_saved"] is True and receipt["failure"] is None
    assert receipt["validates_public_sku_parser"] is False
    parser = Markers()
    parser.feed(body.decode("utf-8"))
    tests = [node for node in parser.nodes if node["id"] == "test"]
    loaded = [node for node in parser.nodes if node["id"] == "loaded"]
    assert len(tests) == 1 and tests[0]["text"].strip() == text, "Test marker differs"
    if mode == "raw":
        assert not loaded, "Raw capture has an actual loaded marker"
    else:
        assert len(loaded) == 1 and loaded[0]["tag"] == "div" and loaded[0]["text"].strip() == "loaded"
print("PASS 2/2 saved owned-fixture captures: hashes, receipts and literal DOM markers; replay API calls=0; SKU parser not validated")
