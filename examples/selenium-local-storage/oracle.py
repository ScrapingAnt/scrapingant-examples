"""Independent literal record oracle; never import the fixture price table here."""
from collections import Counter

EXPECTED_EU = (
    ('SKU-1', 'EUR', 825), ('SKU-2', 'EUR', 1675),
    ('SKU-3', 'EUR', 2425), ('SKU-4', 'EUR', 3350),
)
EXPECTED_US = (
    ('SKU-1', 'USD', 1100), ('SKU-2', 'USD', 2200),
    ('SKU-3', 'USD', 3300), ('SKU-4', 'USD', 4400),
)


def tuples(records):
    if not isinstance(records, list):
        raise ValueError('records must be a list')
    result = []
    for row in records:
        if (not isinstance(row, dict) or set(row) != {'sku', 'currency', 'price_minor'}
                or not isinstance(row['sku'], str) or not isinstance(row['currency'], str)
                or type(row['price_minor']) is not int):
            raise ValueError('malformed record')
        result.append((row['sku'], row['currency'], row['price_minor']))
    return result


def exact_dataset(records, region='eu'):
    if region not in ('eu', 'us'):
        raise ValueError('unknown oracle region')
    return Counter(tuples(records)) == Counter(EXPECTED_EU if region == 'eu' else EXPECTED_US)


def desired_matches(records):
    return sum((Counter(tuples(records)) & Counter(EXPECTED_EU)).values())
