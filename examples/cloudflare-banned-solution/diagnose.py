"""Offline gate for an application expecting a non-empty JSON catalog.

Reads owned response snapshots, never fetches a URL or attempts access recovery.
A possible_1005_page label is text evidence, not Cloudflare authentication.
"""
import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re


def inspect_response(response):
    headers = {key.lower(): value for key, value in response['headers'].items()}
    status = response['status']
    content_type = headers.get('content-type', '').split(';', 1)[0].strip().lower()
    diagnostic = {'status': status, 'content_type': content_type,
                  'ray_id': headers.get('cf-ray', '')}

    def stop(reason):
        return {**diagnostic, 'action': 'stop', 'reason': reason}

    # Stop before parsing or writing records. No automatic retry or proxy switch.
    if not 200 <= status < 300:
        return stop('http_failure')
    if content_type == 'text/html' and re.search(r'\berror\s+1005\b', response['body'], re.I):
        return stop('possible_1005_page')
    if content_type != 'application/json':
        return stop('unexpected_content_type')
    try:
        payload = json.loads(response['body'])
    except (json.JSONDecodeError, TypeError):
        return stop('invalid_json')
    if not isinstance(payload, dict) or set(payload) != {'records'}:
        return stop('invalid_records')
    records = payload['records']
    if not isinstance(records, list) or not records:
        return stop('invalid_records')
    seen = set()
    for row in records:
        if not isinstance(row, dict) or set(row) != {'id', 'name', 'price'}:
            return stop('invalid_records')
        if any(not isinstance(row[key], str) or not row[key].strip() for key in row):
            return stop('invalid_records')
        if row['id'] in seen:
            return stop('invalid_records')
        try:
            price = Decimal(row['price'])
        except InvalidOperation:
            return stop('invalid_records')
        if not price.is_finite() or price < 0:
            return stop('invalid_records')
        seen.add(row['id'])
    return {**diagnostic, 'action': 'accept', 'records': records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    args = parser.parse_args()
    result = inspect_response(json.loads(args.snapshot.read_text()))
    print(json.dumps(result, indent=2))
    return 0 if result['action'] == 'accept' else 2


if __name__ == '__main__':
    raise SystemExit(main())
