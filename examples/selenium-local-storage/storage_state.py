"""Argument-safe CRUD and manual snapshots of one exact origin's localStorage."""
from urllib.parse import urlsplit

SPECIAL_KEY = "pref'line\nλ"
SPECIAL_VALUE = "O'Reilly\nКиїв 🕷"
JSON_VALUE = {'name': SPECIAL_VALUE, 'enabled': False, 'tags': ['eu', None, 3]}


def origin_of(url):
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('an HTTP(S) origin without credentials is required')
    port = parts.port
    host = parts.hostname.lower()
    if ':' in host:
        host = '['+host+']'
    suffix = '' if port in (None, 80 if parts.scheme == 'http' else 443) else ':'+str(port)
    return parts.scheme+'://'+host+suffix


def canonical_origin(value):
    if not isinstance(value, str):
        raise ValueError('origin must be a string')
    origin = origin_of(value)
    if value not in (origin, origin+'/'):
        raise ValueError('supply a canonical origin without path, query or fragment')
    return origin


def set_item(driver, key, value):
    if not isinstance(key, str) or not isinstance(value, str):
        raise ValueError('localStorage helper accepts strings; encode JSON explicitly')
    driver.execute_script('localStorage.setItem(arguments[0], arguments[1]);', key, value)


def get_item(driver, key):
    return driver.execute_script('return localStorage.getItem(arguments[0]);', key)


def remove_item(driver, key):
    driver.execute_script('localStorage.removeItem(arguments[0]);', key)


def snapshot(driver, expected_origin):
    origin = canonical_origin(expected_origin)
    if driver.execute_script('return location.origin;') != origin:
        raise ValueError('current document has a different origin')
    items = driver.execute_script('return Object.keys(localStorage).sort().map(k => [k, localStorage.getItem(k)]);')
    value = {'schema_version': 1, 'origin': origin, 'items': items}
    validate_snapshot(value)
    return value


def validate_snapshot(value):
    if not isinstance(value, dict) or set(value) != {'schema_version', 'origin', 'items'}:
        raise ValueError('invalid snapshot schema')
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('unsupported snapshot version')
    canonical_origin(value['origin'])
    if not isinstance(value['items'], list):
        raise ValueError('snapshot items must be a list')
    keys = []
    for pair in value['items']:
        if not isinstance(pair, list) or len(pair) != 2 or not all(isinstance(x, str) for x in pair):
            raise ValueError('snapshot entries must be string pairs')
        keys.append(pair[0])
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate snapshot key')


def restore(driver, value, expected_origin):
    # Validate all state and both origins before making the first mutation.
    validate_snapshot(value)
    origin = canonical_origin(expected_origin)
    if canonical_origin(value['origin']) != origin or driver.execute_script('return location.origin;') != origin:
        raise ValueError('snapshot and current document must match the exact intended origin')
    driver.execute_script('localStorage.clear(); for (const [key, value] of arguments[0]) localStorage.setItem(key, value);', value['items'])
    return len(value['items'])
