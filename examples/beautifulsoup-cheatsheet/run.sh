#!/usr/bin/env bash
# Every snippet from the article and the cards, run against fixtures/page.html and fixtures/broken.html.
set -uo pipefail
export LC_ALL=C LANG=C PYTHONWARNINGS=default
cd "$(dirname "$0")"; mkdir -p expected_output generated; rm -f expected_output/[0-9]*.txt; status=0
{ echo "python: $(python --version 2>&1)"; python -c "
from importlib.metadata import version; from lxml import etree
for p in ('beautifulsoup4','lxml','html5lib','soupsieve','requests','pandas'): print(p, version(p))
print('libxml2', '.'.join(map(str, etree.LIBXML_VERSION)))"; } > expected_output/00_versions.txt
for script in [0-9][0-9]_*.py; do
  name="${script%.py}"; echo "== $name"
  { echo "\$ python $script"; python "$script" 2>&1; echo "exit=$?"; } > "expected_output/$name.txt"
done
[ "${REFRESH_POPULARITY:-0}" = "1" ] && python popularity.py | tee expected_output/popularity.txt
for f in expected_output/[0-9]*.txt; do echo "=== $f"; cat "$f"; done
g() { grep -q -- "$2" "expected_output/$1"*.txt || { echo "FAILED: $1 missing '$2'"; status=1; }; }
for n in 01 02 03 04 05 06 07 08 09 10 11 12 13; do g $n "exit=0"; done
{ echo "\$ mypy 13_typing.py"; mypy --python-version 3.12 13_typing.py 2>&1; echo "exit=$?"; } > expected_output/13b_mypy.txt; g 13b "Success: no issues"
g 01 "Ant Supply"; g 01 "from_encoding on a str"; g 01 "MarkupResemblesLocatorWarning"
g 02 "--- html5lib"; g 02 "diagnose"; g 03 "Ant Farm Deluxe"; g 03 "soup.find('h9'): None"
g 04 "Out of stock"; g 04 "True"; g 05 "'\\\\n'"; g 06 "KeyError"; g 07 "Back in stock"; g 08 "&amp;"
g 09 "FileNotFoundError"; g 10 "DeprecationWarning"; g 11 "AttributeError"; g 11 "FeatureNotFound"; g 12 "lxml.html + xpath"; g 12 "median"
echo "status=$status"; exit $status
