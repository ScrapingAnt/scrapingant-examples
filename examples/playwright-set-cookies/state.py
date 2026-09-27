"""Independent literal extraction oracle; fixture-specific localStorage adapter."""
from collections import Counter

# Intentionally not imported from the fixture's prices or response builder.
EXPECTED = Counter({
    ('SKU-101', 'EUR', '8.10'): 1,
    ('SKU-202', 'EUR', '16.20'): 1,
    ('SKU-303', 'EUR', '24.30'): 1,
    ('SKU-404', 'EUR', '32.40'): 1,
})


def score_records(rows):
    actual = Counter((r.get('sku'), r.get('currency'), r.get('price')) for r in rows)
    return {
        'row_count': len(rows),
        'expected_records': 4,
        'matching_records': sum((actual & EXPECTED).values()),
        'exact_match': actual == EXPECTED,
    }


def region_params(state, origin):
    """Translate this fixture's exact-origin region into an API query parameter.

    APIRequestContext does not execute the catalog's localStorage-reading JS.
    This is an application-specific adapter, not generic state conversion.
    """
    values = [entry['value']
              for item in state.get('origins', []) if item['origin'] == origin
              for entry in item.get('localStorage', []) if entry['name'] == 'region']
    if len(values) != 1 or values[0] not in ('EU', 'US'):
        raise ValueError('Expected one supported region at the exact fixture origin')
    return {'region': values[0]}
