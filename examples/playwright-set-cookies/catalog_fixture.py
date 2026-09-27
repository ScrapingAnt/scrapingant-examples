"""Self-authored HTTP loopback catalog. Every cookie and record is synthetic."""
from collections import Counter
from contextlib import contextmanager
from decimal import Decimal
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Lock, Thread
from urllib.parse import parse_qs, urlsplit


CATALOG_HTML = b'''<!doctype html><html lang="en"><meta charset="utf-8">
<title>Synthetic catalog</title><link rel="icon" href="data:,">
<table><thead><tr><th>SKU</th><th>Currency</th><th>Price</th></tr></thead><tbody></tbody></table>
<script>
(async () => {
  const region = localStorage.getItem('region') || 'US';
  const response = await fetch('/api/catalog?region=' + encodeURIComponent(region));
  const result = await response.json();
  for (const record of result.records) {
    const row = document.createElement('tr');
    for (const field of ['sku', 'currency', 'price']) {
      const cell = document.createElement('td');
      cell.textContent = record[field]; row.appendChild(cell);
    }
    document.querySelector('tbody').appendChild(row);
  }
  document.body.dataset.ready = 'yes';
})().catch(error => { document.body.dataset.error = error.message; });
</script></html>'''
SEED_HTML = b'''<!doctype html><html><meta charset="utf-8"><title>Seed fixture state</title>
<link rel="icon" href="data:,"><script>localStorage.setItem('region', 'EU');</script>
<body>Synthetic member cookie and EU region are seeded.</body></html>'''


class CatalogFixture:
    def __init__(self):
        self._hits = Counter()
        self._lock = Lock()
        self.origin = None

    def hit_count(self, path):
        with self._lock:
            return self._hits[path]

    def record_hit(self, path):
        with self._lock:
            self._hits[path] += 1


def handler_for(fixture):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            url = urlsplit(self.path)
            fixture.record_hit(url.path)
            headers = {}
            if url.path == '/catalog':
                body, content_type = CATALOG_HTML, 'text/html; charset=utf-8'
            elif url.path == '/seed':
                body, content_type = SEED_HTML, 'text/html; charset=utf-8'
                headers['Set-Cookie'] = 'demo_session=member-v1; Path=/; HttpOnly; SameSite=Lax'
            elif url.path == '/session/guest':
                body, content_type = b'{"changed":true}', 'application/json'
                headers['Set-Cookie'] = 'demo_session=guest-v1; Path=/; HttpOnly; SameSite=Lax'
            elif url.path == '/api/catalog':
                query = parse_qs(url.query)
                jar = SimpleCookie()
                jar.load(self.headers.get('Cookie', ''))
                member = 'demo_session' in jar and jar['demo_session'].value == 'member-v1'
                region = query.get('region', ['US'])[0]
                currency = 'EUR' if region == 'EU' else 'USD'
                factor = Decimal('0.9') if currency == 'EUR' else Decimal('1')
                # Server data/formula are separate from the independent literal oracle.
                base_prices = [('SKU-101', 12, 9), ('SKU-202', 24, 18),
                               ('SKU-303', 36, 27), ('SKU-404', 48, 36)]
                records = [{'sku': sku, 'currency': currency,
                            'price': f'{Decimal(member_price if member else retail_price) * factor:.2f}'}
                           for sku, retail_price, member_price in base_prices]
                body = json.dumps({'audience': 'member' if member else 'retail',
                                   'region': region, 'records': records}).encode()
                content_type = 'application/json'
            elif url.path == '/diagnostic/ping':
                body, content_type = b'{"pong":true}', 'application/json'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            for name, value in headers.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)
    return Handler


@contextmanager
def serve_catalog():
    fixture = CatalogFixture()
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(fixture))
    server.daemon_threads = True
    fixture.origin = f'http://127.0.0.1:{server.server_port}'
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield fixture
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
