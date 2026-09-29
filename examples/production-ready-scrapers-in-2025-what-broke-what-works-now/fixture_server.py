"""Loopback-only deterministic target. Never calls an external service."""
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CATALOG = (Path(__file__).parent / 'fixtures/catalog.html').read_bytes()


class FixtureServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(('127.0.0.1', 0), Handler)
        self.counts = Counter()
        self.observed = []
        self.lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        case = self.path.rsplit('/', 1)[-1]
        with self.server.lock:
            self.server.counts[self.path] += 1
            count = self.server.counts[self.path]
            self.server.observed.append({'path': self.path, 'attempt': count,
                                         'monotonic_s': time.monotonic()})
        status = 200
        body = CATALOG
        headers = {}
        if case in ('401', '403', '404'):
            status = int(case)
            body = b'not available'
        elif case == '503_always' or (case == '503_then_ok' and count == 1):
            status = 503
            body = b'temporary failure'
        elif case == '429_long' or (case == '429_then_ok' and count == 1):
            status = 429
            body = b'rate limited'
            headers['Retry-After'] = '60' if case == '429_long' else '1'
        elif case == 'empty':
            body = b''
        elif case == 'challenge':
            body = b'<h1>Synthetic challenge page; no catalog</h1>'
        elif case == 'malformed':
            body = b'<script id="record">{not-json}</script>'
        elif case == 'missing_price':
            body = CATALOG.replace(b'"price_minor":1299,', b'')
        elif case == 'wrong_type':
            body = CATALOG.replace(b'"price_minor":1299', b'"price_minor":"1299"')
        elif case == 'wrong_currency':
            body = CATALOG.replace(b'"currency":"USD"', b'"currency":"EUR"')
        elif case == 'wrong_price':
            body = CATALOG.replace(b'"price_minor":1299', b'"price_minor":9999')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        try:
            if case == 'stall':
                time.sleep(3.0)
            if case == 'trickle':
                for byte in body:
                    self.wfile.write(bytes([byte]))
                    self.wfile.flush()
                    time.sleep(0.05)
            else:
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # expected: the tested client abandoned a stalled/trickled body


def start():
    server = FixtureServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
