"""Self-authored loopback-only HTTP fixture. No cookies or authentication."""
import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == '/api/catalog':
            region = 'eu' if parse_qs(url.query).get('region') == ['eu'] else 'us'
            # Fixture implementation is independent of oracle.py's literal tuples.
            amounts = (825, 1675, 2425, 3350) if region == 'eu' else (1100, 2200, 3300, 4400)
            currency = 'EUR' if region == 'eu' else 'USD'
            records = [dict(sku=f'SKU-{i}', currency=currency, price_minor=amount)
                       for i, amount in enumerate(amounts, 1)]
            payload = json.dumps(dict(region=region, records=records)).encode()
            self.server.events.append(dict(path=self.path, region=region, status=200, records=records))
            self.send_payload(payload, 'application/json')
        elif url.path == '/catalog':
            self.send_payload((Path(__file__).parent/'fixtures/catalog.html').read_bytes(), 'text/html')
        elif url.path == '/blank':
            self.send_payload(b'<!doctype html><title>Storage bootstrap</title>', 'text/html')
        else:
            self.send_response(404); self.end_headers()

    def send_payload(self, data, kind):
        self.send_response(200)
        self.send_header('Content-Type', kind+'; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers(); self.wfile.write(data)


@contextmanager
def fixture_server():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.events = []
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        yield server, f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown(); server.server_close(); thread.join()
