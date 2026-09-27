"""Self-authored loopback fixture. No secrets, upstream sites or paid calls."""
import json
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlsplit

FIXTURES = Path(__file__).resolve().parent / 'fixtures'


def catalog_response(path):
    parsed = urlsplit(path)
    if parsed.path != '/api/catalog':
        return 404, {'error': 'not found'}
    query = parse_qs(parsed.query, keep_blank_values=True)
    if set(query) - {'region'} or len(query.get('region', ['us'])) != 1:
        return 400, {'error': 'expected one region parameter'}
    region = query.get('region', ['us'])[0]
    if region not in ('eu', 'us'):
        return 400, {'error': 'unknown region'}
    return 200, {'region': region, 'records': json.loads((FIXTURES / 'catalog.json').read_text())[region]}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/':
            status, content_type, body = 200, 'text/html; charset=utf-8', (FIXTURES / 'index.html').read_bytes()
        elif path == '/blank':
            status, content_type, body = 200, 'text/html; charset=utf-8', b'<!doctype html><title>Storage sandbox</title>'
        else:
            status, payload = catalog_response(self.path)
            content_type, body = 'application/json', json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


@contextmanager
def serve_fixture():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
