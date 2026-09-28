"""Independent literals; never derive expected values from the fixture DOM."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROBE = '</script><!--<script> & &amp; "quoted" \\ newline\nКиїв 中文 🕷\u2028\u2029'
RECORDS = [
    {'product': 'Ant Farm Deluxe', 'price': '$1,234.50', 'units': '12,345', 'share': '45.5%'},
    {'product': 'Ant Farm Mini', 'price': '$99.00', 'units': '1,020', 'share': '3.8%'},
    {'product': 'Magnifier', 'price': '$12.25', 'units': '987,654', 'share': '50.7%'},
]
CASES = ['catalog_1', 'catalog_2', 'catalog_3', 'return_only', 'missing_selector', 'delayed']
TARGETS = {
    'catalog': 'https://scrapingant.github.io/scrapingant-examples/fixtures/html-tables.html',
    'delayed': 'https://scrapingant.github.io/scrapingant-examples/fixtures/dynamic-delayed.html',
}

def snippet(case, marker):
    if case not in CASES or not re.fullmatch(r'sa-extract-[a-f0-9]{32}', marker):
        raise ValueError('Invalid case or marker')
    if case == 'return_only':
        return 'return {version:1,ok:true,data:{returned_only:true}};'
    config = {'mode': case, 'marker': marker, 'probe': PROBE,
              'selector': '#absent tbody tr' if case == 'missing_selector' else '#prices tbody tr'}
    return (ROOT / 'snippet.js').read_text().replace('__CONFIG__', json.dumps(config, ensure_ascii=False))

def expected(case):
    if case == 'missing_selector':
        return {'version': 1, 'ok': False, 'error': {'code': 'ELEMENT_MISSING'}}
    if case == 'delayed':
        return {'version': 1, 'ok': True, 'data': {'text': 'I ❤️ ScrapingAnt (after 1500 ms)', 'awaited': True}}
    return {'version': 1, 'ok': True, 'data': {'records': RECORDS, 'transport_probe': PROBE}}

def score(case, result, error):
    if case not in CASES:
        return False
    if case == 'return_only':
        return result is None and error == 'MARKER_COUNT'
    # JSON canonicalization preserves scalar types: Python True == 1 must not pass.
    return error is None and json.dumps(result, sort_keys=True, allow_nan=False) == json.dumps(expected(case), sort_keys=True)
