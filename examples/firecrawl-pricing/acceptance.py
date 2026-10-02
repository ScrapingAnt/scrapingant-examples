"""Original source-grounded semantic checks, with local source path adapted. No I/O except owned source reads."""
import re
from pathlib import Path
from lxml import html
ROOT = Path(__file__).resolve().parent / "sources"

def text_content(node):
    return ''.join(node.itertext())

def norm(s):
    return ' '.join(s.split())

def table_signature(table):
    rows = []
    for row in table.xpath('.//tr'):
        if row.xpath('ancestor::table[1]')[0] is not table:
            continue
        rows.append({'style': row.get('style'), 'cells': [{'tag': c.tag, 'text': norm(text_content(c)), 'rowspan': c.get('rowspan'), 'colspan': c.get('colspan'), 'nested_tables': c.xpath('.//table/@id')} for c in row if c.tag in ('td', 'th')]})
    return rows

def run_checks(record):
    doc = record['result']['structuredContent']
    (md, ht) = (doc['markdown'], doc['html'])
    tree = html.fromstring(ht)
    visible = text_content(tree)
    checks = []

    def check(name, ok, expected):
        checks.append({'check': name, 'passed': bool(ok), 'expected': expected})

    def both(text):
        return text in md.replace('\\|', '|') and text in visible

    def heading(s):
        return f'# {s}' in md and tree.xpath('//h1/text()') == [s]
    fixture = record['fixture']
    lamp = 'AA101 | Desk Lamp | Price: 34.99 USD (3499 minor units).'
    mug = 'BB202 | Ceramic Mug | Price: 12.99 USD (1299 minor units).'
    if fixture == 'complete-catalog':
        check('heading_in_markdown_and_html', heading('Owned synthetic catalog'), 'Owned synthetic catalog')
        check('lamp_identity_price_currency_minor_units', both(lamp), lamp)
        check('mug_identity_price_currency_minor_units', both(mug), mug)
    elif fixture == 'dynamic-delayed':
        delayed = 'I ❤️ ScrapingAnt (after 1500 ms)'
        tests = tree.xpath('//*[@id="test"]')
        loaded = tree.xpath('//*[@id="loaded"]')
        check('rendered_test_element', len(tests) == 1 and text_content(tests[0]) == delayed, delayed)
        check('rendered_loaded_element', len(loaded) == 1 and text_content(loaded[0]) == 'loaded', 'loaded')
        check('rendered_markdown', md.strip() == delayed + '\n\nloaded', delayed + '\n\nloaded')
        check('initial_placeholder_absent_from_output', 'web scraping is hard' not in visible.lower() and 'web scraping is hard' not in md.lower() and (not tree.xpath('//script')), 'Only rendered result; no script body used as evidence')
    elif fixture == 'dynamic-domcontentloaded':
        target = 'I ❤️ ScrapingAnt'
        tests = tree.xpath('//*[@id="test"]')
        check('rendered_test_element', len(tests) == 1 and text_content(tests[0]) == target, target)
        check('rendered_markdown', md.strip() == target, target)
        check('initial_placeholder_absent', 'Web Scraping is hard' not in visible and 'Web Scraping is hard' not in md, 'Initial placeholder absent')
    elif fixture == 'missing-http-404':
        check('target_status_records_404', doc.get('metadata', {}).get('statusCode') == 404, 404)
        check('target_error_records_not_found', doc.get('metadata', {}).get('error') == 'Not Found', 'Not Found')
        check('error_page_content_identifiable', '# 404' in md and 'File not found' in md and (tree.xpath('//h1/text()') == ['404']), 'Recognizable error page, unsuitable as requested data')
    elif fixture == 'html-tables':
        source = html.fromstring((ROOT / 'source-html-tables.html').read_text())
        for st in source.xpath('//table'):
            id_ = st.get('id')
            targets = tree.xpath('//table[@id="' + id_ + '"]')
            check('html_table_structure_' + id_, len(targets) == 1 and table_signature(st) == table_signature(targets[0]), 'Source cell text, spans, nested-table membership and hidden-row style preserved')
        simple_rows = ['| Ada | 36 | London |', '| Grace | 45 | Arlington |', '| Linus | 28 | Helsinki |']
        check('markdown_simple_rows', all((x in md for x in simple_rows)), simple_rows)
        codes = ['| 007 | 01234 | agent |', '| 042 | 00501 | answer |']
        check('markdown_leading_zero_strings', all((x in md for x in codes)), codes)
        prices = ['| Ant Farm Deluxe | $1,234.50 | 12,345 | 45.5% |', '| Ant Farm Mini | $99.00 | 1,020 | 3.8% |', '| Magnifier | $12.25 | 987,654 | 50.7% |']
        check('markdown_currency_percent_grouped_numbers', all((x in md for x in prices)), prices)
        dates = ['| 2026-09-01 | 2026-09-03 | 3 |', '| 2026-09-10 | 2026-09-15 | 1 |']
        check('markdown_date_strings', all((x in md for x in dates)), dates)
        links = ['[Product](https://scrapingant.github.io/docs/product)', '[manual](https://example.com/deluxe)']
        check('markdown_links', all((x in md for x in links)), links)
        euros = ['| Germany | 1.234.567,89 | 3,5 |', '| France | 987.654,32 | -1,2 |', '| Spain | n/a | 0,0 |']
        check('markdown_european_number_strings', all((x in md for x in euros)), euros)
    elif fixture == 'markdown-article':
        check('heading_in_markdown_and_html', heading('Ant Farm Deluxe review'), 'Ant Farm Deluxe review')
        rows = [[text_content(cell) for cell in row] for row in tree.xpath('//table/tbody/tr')]
        expected_rows = [('Chamber volume', '1.8', 'litre'), ('Tunnel length after 6 weeks', '142', 'cm'), ('Price paid', '39.90', 'USD')]
        for (i, row) in enumerate(expected_rows, 1):
            check(f'table_row_{i}_in_markdown_and_html', list(row) in rows and '| ' + ' | '.join(row) + ' |' in md, list(row))
        code = 'def feed(day):\n    return "honey water" if day % 2 == 0 else "seed mix"'
        check('code_block_content_and_indentation', tree.xpath('//pre/code/text()') == [code] and '```\n' + code + '\n```' in md, code)
        url = 'https://scrapingant.github.io/guides/harvester-ants'
        anchors = tree.xpath('//a[@href="' + url + '"]')
        check('care_guide_label_and_root_relative_resolution', any((text_content(a) == 'harvester ant care guide' for a in anchors)) and f'[harvester ant care guide]({url})' in md, url)
    elif fixture == 'missing-price':
        missing = 'BB202 | Ceramic Mug | Price: unavailable; currency: USD.'
        check('heading_in_markdown_and_html', heading('Owned synthetic catalog'), 'Owned synthetic catalog')
        check('lamp_identity_price_currency_minor_units', both(lamp), lamp)
        check('mug_missingness_preserved', both(missing), missing)
        check('known_complete_fixture_price_not_inferred', '12.99' not in md and '12.99' not in visible and ('1299' not in md) and ('1299' not in visible), 'Missing mug price stays missing')
        numeric_records = re.findall('(AA101|BB202)\\s*\\|[^\\n]*?Price:\\s*(\\d+\\.\\d{2})\\s+USD\\s*\\((\\d+) minor units\\)', md.replace('\\|', '|'))
        complete_contract = set((r[0] for r in numeric_records)) == {'AA101', 'BB202'}
        check('downstream_both_numeric_prices_contract_rejects', not complete_contract and set((r[0] for r in numeric_records)) == {'AA101'}, 'Deterministic local completeness gate rejects missing mug price; this is not a Firecrawl JSON extraction test')
    return checks
