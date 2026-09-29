"""Independent hand-authored case expectations, plus malformed-input regressions."""
import json
from pathlib import Path
import tempfile
from check_declarations import ROOT, build_report, load_sellers

report = build_report()
oracle = json.loads((ROOT / 'fixtures/oracle.json').read_text())
actual = {str(row['line']): [row['status'], row['reason']] for row in report['rows']}
assert actual == oracle['by_line'], (actual, oracle['by_line'])
assert report['counts'] == oracle['counts'], report['counts']
by_line = {row['line']: row for row in report['rows']}
assert by_line[3]['seller_id'] == '00123'
assert by_line[3]['matches'][0]['business_domain'] == 'publisher-business.example'
assert by_line[3]['publisher'] == 'publisher.example'
assert by_line[3]['certification_id'] == 'cert-demo'
assert by_line[4]['relationship'] == 'RESELLER'
assert by_line[18]['relationship'] == 'DIRECT'
assert by_line[18]['matches'][0]['seller_type'] == 'BOTH'
assert by_line[8]['duplicate_of'] == 3
assert [m['seller_index'] for m in by_line[7]['matches']] == [3, 4]
assert by_line[6]['matches'][0]['is_confidential'] == 1
assert by_line[6]['matches'][0]['name'] is None
assert report['variables'][1]['value'] == 'manager.example, GB'
assert all(not row['interpreted'] for row in report['variables'])
assert all(len(src['sha256']) == 64 for src in report['sources']['sellers'].values()
           if src['sha256'] is not None)

# A malformed unrelated record must also block negative lookup conclusions.
malformed = [
    ('{"version":"1.0","sellers":[],"sellers":[]}', 'invalid_json'),
    ('{"version":"1.0","sellers":[NaN]}', 'invalid_json'),
    ('{"version":"1.0","sellers":[{"seller_id":"ok","seller_type":"PUBLISHER","name":"A"},{}]}', 'invalid_sellers_schema'),
    ('{"version":"1.0","sellers":[{"seller_id":"a","seller_type":"PUBLISHER","is_confidential":"1"}]}', 'invalid_sellers_schema'),
    ('{"version":"2.0","sellers":[]}', 'invalid_sellers_schema'),
]
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / 'regression.json'
    for body, expected in malformed:
        path.write_text(body)
        index, error, provenance = load_sellers(path)
        assert index is None and error == expected, (body, error)
        assert provenance['sha256']
print(f"Fixture classifications: {len(actual)}/{len(oracle['by_line'])} matched the independent oracle.")
print(f"Malformed-input regressions: {len(malformed)}/{len(malformed)} rejected before lookup.")
print('Leading-zero IDs, independent relationship/type labels, provenance, variables and duplicate handling: passed.')
