"""Reproduce owned snapshot matrix and capture actual classifier output."""
import json
from pathlib import Path
from diagnose import inspect_response

root = Path(__file__).parent
expected = {'valid-json': ('accept', None), 'denied-403': ('stop', 'http_failure'),
            'denied-200': ('stop', 'possible_1005_page'),
            'challenge-200': ('stop', 'unexpected_content_type'),
            'error-json-200': ('stop', 'invalid_records'),
            'duplicate-json': ('stop', 'invalid_records')}
results = []
for name, (action, reason) in expected.items():
    result = inspect_response(json.loads((root/'fixtures'/f'{name}.json').read_text()))
    assert result['action'] == action and result.get('reason') == reason, name
    if action == 'stop':
        assert 'records' not in result
    else:
        assert result['records'] == [{'id':'A1','name':'Widget','price':'12.50'}]
    results.append({'case': name, **result})
(root/'expected_output').mkdir(exist_ok=True)
(root/'expected_output'/'matrix.json').write_text(json.dumps(results, indent=2)+'\n')
print('Owned snapshots: 6; accepted: 1; stopped: 5; outbound requests: 0')
for row in results:
    print(f"{row['case']}: {row['action']} ({row.get('reason', 'valid_records')})")
