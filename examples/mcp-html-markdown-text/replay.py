#!/usr/bin/env python3
"""Offline reference transformations and lexical survival; no API/model calls."""
import argparse
import base64
import csv
import hashlib
import importlib.metadata
import json
import platform
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import html2text
import tiktoken
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from contract import TRUTH

ROOT = Path(__file__).resolve().parent
ARMS = ("html", "markdown", "text")
SOURCE_URLS = {
    "catalog": "https://scrapingant.github.io/scrapingant-examples/fixtures/html-tables.html",
    "links": "https://catalog.example/lamps",
    "attributes": "https://catalog.example/bottles",
}
SELECTION = """() => {
  const selection = window.getSelection();
  const range = document.createRange();
  range.selectNode(document.documentElement);
  selection.removeAllRanges();
  selection.addRange(range);
  return selection.toString();
}"""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def markdown(source):
    soup = BeautifulSoup(source, "html.parser")
    for tag in soup(["script", "noscript"]):
        tag.decompose()
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    return converter.handle(str(soup))


def formats(source, page):
    page.set_content(source, wait_until="domcontentloaded")
    return {"html": source, "markdown": markdown(source), "text": page.evaluate(SELECTION)}


def retained_slots(case, value):
    rows = []
    for index, record in enumerate(TRUTH[case]):
        for field, expected in record.items():
            if expected is None:
                continue  # nulls cannot inflate preservation
            candidates = [expected]
            if field == "buy_url":
                candidates.append(urlparse(expected).path)
            rows.append({"record": index, "field": field, "expected": expected,
                         "literal_present": any(s in value for s in candidates)})
    return rows


def encoding_hash(encoding):
    entries = sorted(encoding._mergeable_ranks.items(), key=lambda x: x[1])
    canonical = b"".join(base64.b64encode(token) + b" " + str(rank).encode() + b"\n"
                         for token, rank in entries)
    return sha(canonical)


def run(out):
    out.mkdir(parents=True, exist_ok=True)
    encodings = {n: tiktoken.get_encoding(n) for n in ("o200k_base", "cl100k_base")}
    report = {
        "measurement": "offline_reference_lexical_survival_not_llm_accuracy",
        "transform_repeats": 5, "api_calls": 0, "model_calls": 0,
        "token_scope": "exact representation content; prompts/schema/tool envelopes excluded",
        "environment": {"python": platform.python_version(), "os": platform.platform(),
                        **{p: importlib.metadata.version(p) for p in
                           ("beautifulsoup4", "soupsieve", "html2text", "tiktoken", "playwright")}},
        "tokenizers": {n: {"mergeable_ranks_sha256": encoding_hash(e),
                           "ordinary_token_count": len(e._mergeable_ranks)} for n, e in encodings.items()},
        "sources": {}, "rows": [], "counterfactuals": [],
        "ground_truth_sha256": sha((ROOT / "ground_truth.json").read_bytes()),
        "task_sha256": sha((ROOT / "task.txt").read_bytes()),
        "runtime_sha256": {n: sha((ROOT / n).read_bytes()) for n in ("replay.py", "contract.py", "requirements.txt")},
    }
    with sync_playwright() as p:
        browser = p.chromium.launch()
        report["environment"]["chromium"] = browser.version
        context = browser.new_context(java_script_enabled=False)
        context.route("**/*", lambda route: route.abort())
        page = context.new_page()
        for case in TRUTH:
            source_bytes = (ROOT / "fixtures" / f"{case}.html").read_bytes()
            source = source_bytes.decode("utf-8", errors="strict")
            report["sources"][case] = {"sha256": sha(source_bytes), "source_url": SOURCE_URLS[case],
                                      "origin": "existing_non_sensitive_capture" if case == "catalog" else "local_authored_fixture"}
            repeats = [formats(source, page) for _ in range(5)]
            for arm in ARMS:
                value = repeats[0][arm]
                data = value.encode("utf-8")
                slots = retained_slots(case, value)
                output_file = f"{case}.{arm}"
                (out / output_file).write_bytes(data)
                hashes = [sha(v[arm].encode("utf-8")) for v in repeats]
                row = {"case": case, "arm": arm, "utf8_bytes": len(data), "unicode_codepoints": len(value),
                       "o200k_base": len(encodings["o200k_base"].encode(value, disallowed_special=())),
                       "cl100k_base": len(encodings["cl100k_base"].encode(value, disallowed_special=())),
                       "present_slots": sum(s["literal_present"] for s in slots), "expected_non_null_slots": len(slots),
                       "slots": slots, "sha256": sha(data), "repeat_sha256": hashes,
                       "byte_deterministic_in_five_local_repeats": len(set(hashes)) == 1, "output_file": output_file}
                report["rows"].append(row)
            if case != "catalog":
                replacement = (source.replace("/buy/lamp-a", "/buy/different-a").replace("/buy/lamp-b", "/buy/different-b")
                               if case == "links" else source.replace("BOTTLE-RED", "CHANGED-RED").replace("BOTTLE-BLUE", "CHANGED-BLUE"))
                changed = formats(replacement, page)
                (out / f"{case}.counterfactual.html").write_text(replacement)
                for arm in ARMS:
                    (out / f"{case}.counterfactual.{arm}").write_text(changed[arm])
                report["counterfactuals"].append({"case": case,
                    "changed_field": "buy_url" if case == "links" else "sku",
                    "outputs_identical": {arm: repeats[0][arm] == changed[arm] for arm in ARMS},
                    "original_source_sha256": sha(source_bytes), "changed_source_sha256": sha(replacement.encode())})
        browser.close()
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    with (out / "summary.csv").open("w", newline="") as f:
        columns = ["case", "arm", "utf8_bytes", "unicode_codepoints", "o200k_base", "cl100k_base", "present_slots", "expected_non_null_slots"]
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report["rows"])
    lines = ["OFFLINE REFERENCE: lexical survival and content tokenization, NOT model accuracy or live MCP."]
    for row in report["rows"]:
        lines.append(f"{row['case']:10} {row['arm']:8} {row['utf8_bytes']:5} bytes {row['unicode_codepoints']:5} codepoints "
                     f"{row['o200k_base']:4} o200k {row['cl100k_base']:4} cl100k "
                     f"{row['present_slots']}/{row['expected_non_null_slots']} required non-null slots present")
    lines.append("Paid API/model calls: 0. LLM exact-record accuracy and live MCP costs: unmeasured.")
    (out / "summary.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return report


def verify():
    expected = json.loads((ROOT / "expected_output" / "report.json").read_text())
    with tempfile.TemporaryDirectory() as d:
        actual = run(Path(d))
        assert actual["rows"] == expected["rows"], "representation/slot/token mismatch"
        for key in ("sources", "counterfactuals", "ground_truth_sha256", "task_sha256", "runtime_sha256", "tokenizers"):
            assert actual[key] == expected[key], f"{key} mismatch"
        for row in expected["rows"]:
            assert sha((ROOT / "expected_output" / row["output_file"]).read_bytes()) == row["sha256"], "saved output changed"
    print("PASS: frozen source, task/oracle/runtime hashes, all nine outputs, tokens, slots and counterfactuals replay exactly.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "run_output")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    verify() if args.verify else run(args.out)
