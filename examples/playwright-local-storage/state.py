"""Independent literal oracle and one exact-origin initializer (no fixture imports)."""
import json
from collections import Counter
from urllib.parse import urlsplit

# Authored independently of fixtures/catalog.json. Strings preserve displayed cents.
EXPECTED_EU = (
    ('ATLAS-01', 'EUR', '12.50'), ('BIRCH-02', 'EUR', '24.00'),
    ('CORAL-03', 'EUR', '8.75'), ('DELTA-04', 'EUR', '41.20'),
)
EXPECTED_US = (
    ('ATLAS-01', 'USD', '14.00'), ('BIRCH-02', 'USD', '27.00'),
    ('CORAL-03', 'USD', '10.00'), ('DELTA-04', 'USD', '46.00'),
)


def record_tuples(records):
    if not isinstance(records, list):
        raise ValueError('Records must be a list')
    rows = []
    for row in records:
        if not isinstance(row, dict) or set(row) != {'sku', 'currency', 'price'}:
            raise ValueError('Every record needs exactly sku, currency and price')
        if any(type(value) is not str for value in row.values()):
            raise ValueError('Record fields must be strings')
        rows.append((row['sku'], row['currency'], row['price']))
    return rows


def score_records(records):
    actual, expected = Counter(record_tuples(records)), Counter(EXPECTED_EU)
    return {'row_count': len(records), 'matching_records': sum((actual & expected).values()),
            'exact_match': actual == expected}


def validate_origin(origin):
    parsed = urlsplit(origin)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1'
            or parsed.username or parsed.password or not parsed.port
            or parsed.path or parsed.query or parsed.fragment
            or origin != f'http://127.0.0.1:{parsed.port}'):
        raise ValueError('Expected a canonical HTTP loopback origin with an explicit port')
    return origin


def init_script(origin, region='eu', missing_only=True):
    validate_origin(origin)
    if region not in ('eu', 'us') or type(missing_only) is not bool:
        raise ValueError('Expected a supported region and a boolean missing_only flag')
    config = json.dumps({'origin': origin, 'key': 'region', 'region': region,
                         'missing_only': missing_only})
    return '''(() => {
  const config = CONFIG;
  if (location.origin !== config.origin) return;
  if (!config.missing_only || localStorage.getItem(config.key) === null) {
    localStorage.setItem(config.key, config.region);
  }
})();'''.replace('CONFIG', config)
