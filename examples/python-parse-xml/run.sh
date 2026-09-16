#!/usr/bin/env bash
# Every example from the article, run against the fixtures in fixtures/ (and a generated large file).
set -uo pipefail
cd "$(dirname "$0")"; rm -rf expected_output; mkdir -p expected_output generated; status=0
{ echo "python: $(python --version 2>&1)"; python -c "
from importlib.metadata import version; import pyexpat; from lxml import etree
print('expat', pyexpat.EXPAT_VERSION); print('lxml', version('lxml'), '(libxml2', '.'.join(map(str, etree.LIBXML_VERSION)) + ')')
for p in ('beautifulsoup4','untangle','xmltodict','defusedxml','pandas'): print(p, version(p))"; } > expected_output/00_versions.txt
for script in [0-9][0-9]_*.py; do
  name="${script%.py}"; echo "== $name"
  { echo "\$ python $script"; python "$script" 2>&1; echo "exit=$?"; } > "expected_output/$name.txt"
done
for f in expected_output/*.txt; do echo "=== $f"; cat "$f"; done
g() { grep -q -- "$2" "expected_output/$1"*.txt || { echo "FAILED: $1 missing '$2'"; status=1; }; }
for n in 01 02 03 04 05 06 07 08 09 10; do g $n "exit=0"; done
g 01 "bk101 XML Developer's Guide 44.95"; g 01 "Contains <b>markup</b> & ampersands"
g 02 "findall('url'): \[\]"; g 02 "<ns0:url xmlns:"; g 04 "issubclass(ET.ParseError, SyntaxError): True"; g 09 "400,000 <record>"; g 02 "3 wildcard: \['https://example.com/'"
g 03 "declaration honoured): Jürgen"; g 03 "UnicodeDecodeError"; g 03 "ValueError: Unicode strings with encoding declaration"
g 04 "ParseError.position"; g 04 "XMLSyntaxError.lineno"; g 04 "recover=True: <catalog>"
g 06 "books.xml valid: True"; g 06 "books-invalid.xml valid: False"; g 06 "iterparse books: \['bk101', 'bk102', 'bk103'\]"
g 07 "pandas columns"; g 08 "Maeve Ascendant (2nd ed.)"
g 09 "ET.iterparse + clear"; g 09 "lxml.iterparse + clear"
g 10 "defusedxml.ElementTree.parse(billion-laughs): defusedxml.common.EntitiesForbidden"; g 10 "this-is-the-secret-file-content"
echo "status=$status"; exit $status
