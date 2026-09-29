"""A bounded local HTTP acquisition example; not a general crawler framework."""
import asyncio
import hashlib
import json
import random
import sqlite3
import time
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

import httpx
from jsonschema import Draft202012Validator

MAX_ATTEMPTS = 3
JOB_SECONDS = 6.0
IO_SECONDS = 1.0
MAX_BODY_BYTES = 65536
SCHEMA = json.loads((Path(__file__).parent / 'fixtures/record.schema.json').read_text())
VALIDATOR = Draft202012Validator(SCHEMA)


def retry_after_seconds(value, now):
    if not value:
        return None
    if value.isascii() and value.isdecimal():
        # Avoid integer conversion limits; a huge valid wait cannot fit our budget.
        return float(value) if len(value) < 12 else 1e12
    try:
        stamp = parsedate_to_datetime(value)
        if stamp.tzinfo is None:
            return None
        return max(0.0, stamp.timestamp() - now)
    except (ValueError, TypeError, OverflowError):
        return None


class RecordScript(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.inside = False
        self.count = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('id') == 'record':
            self.count += 1
            self.inside = True

    def handle_endtag(self, tag):
        if tag == 'script':
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.parts.append(data)


def extract(body):
    parser = RecordScript()
    parser.feed(body.decode('utf-8', errors='strict'))
    if parser.count != 1:
        raise ValueError('expected exactly one record script')
    return json.loads(''.join(parser.parts))


async def scrape(client, url, sink, emit, *, rng):
    """Only direct GETs. One retry layer; IO timeout plus an absolute job deadline."""
    started = time.monotonic()
    attempts = 0
    loop = asyncio.get_running_loop()
    deadline = loop.time() + JOB_SECONDS

    def event(kind, **fields):
        emit({'event': kind, 'attempt': attempts,
              'elapsed_s': round(time.monotonic() - started, 6), **fields})

    def finish(outcome, **fields):
        event('terminal', outcome=outcome, **fields)
        return {'outcome': outcome, 'attempts': attempts,
                'elapsed_s': round(time.monotonic() - started, 6)}

    async def run():
        nonlocal attempts
        for attempts in range(1, MAX_ATTEMPTS + 1):
            event('attempt_started')
            retry_after = None
            try:
                async with client.stream('GET', url) as response:
                    status = response.status_code
                    retry_after = retry_after_seconds(response.headers.get('retry-after'), time.time())
                    event('response', status=status)
                    if status in (429, 500, 502, 503, 504):
                        reason = f'http_{status}'
                    elif status != 200:
                        return finish('terminal_http', status=status)
                    else:
                        chunks = bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(chunks) + len(chunk) > MAX_BODY_BYTES:
                                return finish('body_too_large')
                            chunks.extend(chunk)
                        event('body', bytes=len(chunks), sha256=hashlib.sha256(chunks).hexdigest(),
                              preview_utf8=chunks[:320].decode('utf-8', errors='replace'))
                        try:
                            record = extract(chunks)
                        except (ValueError, UnicodeError):
                            return finish('content_invalid')
                        errors = sorted(error.message for error in VALIDATOR.iter_errors(record))
                        event('schema', passed=not errors, errors=errors)
                        if errors:
                            return finish('schema_invalid')
                        # A declared business requirement, not a universal currency rule.
                        if record['currency'] != 'USD':
                            return finish('business_invalid', reason='this feed requires USD')
                        try:
                            with sink:
                                cursor = sink.execute('INSERT INTO records VALUES (?, ?) ON CONFLICT(id) DO NOTHING',
                                                      (record['id'], json.dumps(record, sort_keys=True)))
                            event('delivery', inserted=cursor.rowcount, record_id=record['id'])
                            return finish('delivered' if cursor.rowcount else 'duplicate')
                        except sqlite3.Error as error:
                            return finish('delivery_failed', error=type(error).__name__)
            except (httpx.TimeoutException, httpx.NetworkError) as error:
                reason = type(error).__name__
                event('transport_error', error=reason)
            if attempts == MAX_ATTEMPTS:
                return finish('attempt_limit', reason=reason)
            backoff = rng.uniform(0, min(0.2, 0.05 * 2 ** (attempts - 1)))
            delay = max(backoff, retry_after if retry_after is not None else 0)
            if loop.time() + delay >= deadline:
                return finish('retry_deferred', reason=reason, requested_wait_s=delay)
            event('retry_wait', reason=reason, seconds=delay)
            await asyncio.sleep(delay)
        raise AssertionError('unreachable')

    try:
        async with asyncio.timeout_at(deadline):
            return await run()
    except TimeoutError:
        return finish('deadline')


def make_sink():
    sink = sqlite3.connect(':memory:', timeout=0)
    sink.execute('CREATE TABLE records (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    return sink
