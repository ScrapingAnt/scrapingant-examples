#!/usr/bin/env bash
# Every option and error from the article, run against fixtures/tables.html (and its copy served from GitHub Pages).
set -uo pipefail
export LC_ALL=C LANG=C
cd "$(dirname "$0")"; mkdir -p expected_output; rm -f expected_output/[0-9]*.txt; status=0
{ echo "python: $(python --version 2>&1)"; python -c "
from importlib.metadata import version; from lxml import etree
for p in ('pandas','numpy','lxml','beautifulsoup4','html5lib','requests'): print(p, version(p))
print('libxml2', '.'.join(map(str, etree.LIBXML_VERSION)))"; } > expected_output/00_versions.txt
for script in [0-9][0-9]*_*.py; do
  name="${script%.py}"; echo "== $name"
  { echo "\$ python $script"; python "$script" 2>&1; echo "exit=$?"; } > "expected_output/$name.txt"
done
for f in expected_output/[0-9]*.txt; do echo "=== $f"; cat "$f"; done
g() { grep -qF -- "$2" "expected_output/$1"*.txt || { echo "FAILED: $1 missing '$2'"; status=1; }; }
for n in 01 02 03 04 05 06 07 08 09 10; do g $n "exit=0"; done
g 01 "FileNotFoundError"; g 01 "pd.read_html(URL): 12"; g 02 "No tables found"; g 03 "MultiIndex"; g 03 "Tweezers"
g 04 "007"; g 04 "1234567.89"; g 05 "https://example.com/deluxe"; g 06 "AF-2"; g 07 "median"; g 07 "ImportError"
g 08 "pd.read_html(StringIO(r.text)): 12"; g 09 "AttributeError"; g 09 "TypeError"
echo "status=$status"; exit $status
