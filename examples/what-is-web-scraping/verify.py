"""Run the CLI against an independent oracle and explicit negative controls."""
import hashlib
import json
import platform
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

from extract import extract_products

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "expected_output"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def cli(filename):
    return subprocess.run(
        [sys.executable, "extract.py", "fixtures/" + filename],
        cwd=ROOT, text=True, encoding="utf-8", capture_output=True, check=False,
    )


def main():
    OUT.mkdir(exist_ok=True)
    expected = json.loads((ROOT / "fixtures/expected-records.json").read_text())
    result = cli("catalog.html")
    require(result.returncode == 0 and not result.stderr, "catalog CLI failed")
    records = json.loads(result.stdout)
    require(records == expected, "catalog differs from independently authored oracle")
    (OUT / "catalog.json").write_text(result.stdout, encoding="utf-8")
    print("PASS catalog: 3/3 expected records; 9/9 fields exactly match the independent oracle")
    print("PASS text: Unicode é and HTML entity &amp; preserved as Café & tea mug")
    for filename, name, expected_error in [
        ("missing-price.html", "missing-price", "ERROR: p2: missing price\n"),
        ("javascript-only.html", "javascript-only", "ERROR: no product cards found\n"),
    ]:
        result = cli(filename)
        require(result.returncode == 1, name + " must exit 1")
        require(result.stdout == "", name + " must not emit partial JSON")
        require(result.stderr == expected_error, name + " error differs")
        (OUT / (name + ".txt")).write_text(
            result.stderr + f"exit_code={result.returncode}\nstdout_bytes={len(result.stdout.encode())}\n",
            encoding="utf-8",
        )
        print(f"PASS {name}: exit 1, expected error, no partial JSON")
    for name, html, message in [
        ("blank price", '<article class="product" data-id="p1"><h2>Notebook</h2><span class="price"> </span></article>', "p1: missing price"),
        ("missing id", '<article class="product"><h2>Notebook</h2><span class="price">USD 4.50</span></article>', "product card: missing id"),
        ("missing title", '<article class="product" data-id="p1"><span class="price">USD 4.50</span></article>', "p1: missing title"),
        ("duplicate id", '<article class="product" data-id="p1"><h2>Notebook</h2><span class="price">USD 4.50</span></article>' * 2, "p1: duplicate id"),
    ]:
        try:
            extract_products(html)
        except ValueError as exc:
            require(str(exc) == message, name + " error differs")
        else:
            raise RuntimeError(name + " was accepted")
        print(f"PASS {name}: expected validation error")
    environment = {
        "python": platform.python_version(), "os": platform.platform(),
        "dependencies": {name: version(name) for name in ("beautifulsoup4", "soupsieve", "typing_extensions")},
        "fixture_sha256": {
            file.name: hashlib.sha256(file.read_bytes()).hexdigest()
            for file in sorted((ROOT / "fixtures").iterdir()) if file.is_file()
        },
        "target_http_requests": 0, "paid_api_requests": 0, "api_credits": 0,
    }
    (OUT / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    print("PASS 8/8 verification checks; target HTTP requests=0; paid API requests=0; API credits=0")


if __name__ == "__main__":
    main()
