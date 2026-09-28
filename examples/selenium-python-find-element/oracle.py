"""Literal oracle: never imported by the HTML fixture or used to build its DOM."""
FIELDS = ('sku', 'title', 'currency', 'price', 'href', 'badge')
EXPECTED = (
    ('C-101', 'Café & Cocoa', 'USD', '12.50', '/products/cafe', 'New'),
    ('T-202', 'Tea "No. 2"', 'EUR', '8.00', '/products/tea', None),
    ('N-303', 'Notebook <A5>', 'GBP', '5.25', '/products/notebook', 'Sale'),
)
OUTSIDE = ('D-OUT', 'Outside decoy', 'USD', '0.01', '/products/outside', None)
INACTIVE = ('D-IN', 'Inactive decoy', 'USD', '0.02', '/products/inactive', None)


def exact_records(records, expected=EXPECTED):
    if not isinstance(records, list) or len(records) != len(expected):
        return False
    rows = []
    for record in records:
        if not isinstance(record, dict) or set(record) != set(FIELDS):
            return False
        if any(not isinstance(record[key], str) for key in FIELDS[:-1]):
            return False
        if record['badge'] is not None and not isinstance(record['badge'], str):
            return False
        rows.append(tuple(record[key] for key in FIELDS))
    return len({row[0] for row in rows}) == len(rows) and set(rows) == set(expected)


def has_class_token(classes, token):
    return token in classes.split()
