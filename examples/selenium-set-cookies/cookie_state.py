"""A deliberately narrow, exact-origin JSON snapshot, not a browser profile."""
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlsplit


def origin_of(url):
    u = urlsplit(url)
    if u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password:
        raise ValueError('Expected an HTTP(S) origin without credentials')
    port = u.port or (443 if u.scheme == 'https' else 80)
    return (u.scheme, u.hostname.lower(), port)


def checked_cookie(cookie, host):
    if not isinstance(cookie, dict):
        raise ValueError('Expected cookie object')
    domain = cookie.get('domain', host)
    if not isinstance(domain, str) or domain.lstrip('.').lower() != host:
        raise ValueError('Snapshot helper permits only the exact source host')
    name, value = cookie.get('name'), cookie.get('value')
    if not isinstance(name, str) or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name):
        raise ValueError('Invalid cookie name')
    if not isinstance(value, str) or any(ord(c) < 33 or ord(c) > 126 or c in '\";,\\' for c in value):
        raise ValueError('This helper requires an unquoted ASCII cookie value')
    result = {'name': name, 'value': value}
    for key in ('path', 'secure', 'httpOnly', 'sameSite', 'expiry'):
        if key in cookie: result[key] = cookie[key]
    if 'path' in result and (not isinstance(result['path'], str) or not result['path'].startswith('/')):
        raise ValueError('Invalid cookie path')
    for key in ('secure', 'httpOnly'):
        if key in result and not isinstance(result[key], bool): raise ValueError('Invalid cookie flag')
    if 'sameSite' in result and result['sameSite'] not in ('Strict', 'Lax', 'None'):
        raise ValueError('Invalid SameSite value')
    if 'expiry' in result and (type(result['expiry']) is not int or result['expiry'] < 0):
        raise ValueError('Expiry must be nonnegative integer Unix seconds')
    # Omit Domain deliberately: restoration is limited to this exact host.
    return result


def save_snapshot(driver, path, expected_origin):
    origin = origin_of(expected_origin)
    if origin_of(driver.current_url) != origin:
        raise ValueError('Current document is not on the expected origin')
    cookies = driver.get_cookies()
    for cookie in cookies: checked_cookie(cookie, origin[1])
    payload = {'version': 1, 'origin': expected_origin, 'cookies': cookies}
    fd = os.open(Path(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'w') as f:
        if os.name == 'posix': os.fchmod(f.fileno(), 0o600)
        json.dump(payload, f, indent=2)
        f.write('\n')


def restore_snapshot(driver, path, expected_origin, *, now=None):
    origin = origin_of(expected_origin)
    if origin_of(driver.current_url) != origin:
        raise ValueError('Navigate to and verify the target origin before restoring')
    payload = json.loads(Path(path).read_text())
    if payload.get('version') != 1 or origin_of(payload.get('origin', '')) != origin:
        raise ValueError('Snapshot belongs to another origin or format')
    if not isinstance(payload.get('cookies'), list): raise ValueError('Missing cookies list')
    cookies = [checked_cookie(c, origin[1]) for c in payload['cookies']]
    now = time.time() if now is None else now
    stats = {'restored': 0, 'skipped_expired': 0}
    for cookie in cookies:
        if cookie.get('expiry', float('inf')) <= now:
            stats['skipped_expired'] += 1
            continue
        driver.add_cookie(cookie)
        stats['restored'] += 1
    return stats
