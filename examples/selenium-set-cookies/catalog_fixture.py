"""Synthetic HTTPS catalog. Demo cookies are not real credentials."""
import html
import json
import ssl
import subprocess
import tempfile
import threading
from contextlib import contextmanager
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

# Deliberately distinct tables; not a live exchange-rate calculation.
PRICES = {
    ('member', 'EUR'): [800, 1600, 2400, 3200],
    ('retail', 'EUR'): [1000, 2000, 3000, 4000],
    ('member', 'USD'): [900, 1800, 2700, 3600],
    ('retail', 'USD'): [1200, 2400, 3600, 4800],
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def do_GET(self):
        path = urlsplit(self.path).path
        jar = SimpleCookie(); jar.load(self.headers.get('Cookie', ''))
        cookies = {k: v.value for k, v in jar.items()}
        member = cookies.get('demo_session') == 'issued-by-fixture' and self.server.session_active
        tier = 'member' if member else 'retail'
        currency = 'EUR' if cookies.get('demo_region') == 'eu' else 'USD'
        self.send_response(200)
        self.server.events.append({'path': path, 'status': 200, 'tier': tier, 'currency': currency})
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        if path == '/seed':
            self.server.session_active = True
            self.send_header('Set-Cookie', 'demo_session=issued-by-fixture; Path=/; Max-Age=3600; Secure; HttpOnly; SameSite=Lax')
            self.send_header('Set-Cookie', 'demo_region=eu; Path=/; Max-Age=3600; Secure; SameSite=Lax')
        self.end_headers()
        if path.startswith('/catalog/'):
            rows = ''.join(f'<tr data-sku="SKU-{i}"><td>{i}</td><td class="currency">{currency}</td><td class="price">{price}</td></tr>'
                           for i, price in enumerate(PRICES[(tier, currency)], 1))
            page = f'<h1>Synthetic catalog</h1><p id="tier">{tier}</p><table id="products">{rows}</table>'
        else:
            page = '<h1>Cookie fixture</h1>'
        # Named cookies only; never reflect arbitrary cookies or request headers.
        names = sorted(k for k in cookies if k in ('demo_region', 'demo_session'))
        page += f'<div id="received-cookie-names" data-names="{html.escape(json.dumps(names), quote=True)}"></div>'
        self.wfile.write(('<!doctype html><html><body>'+page+'</body></html>').encode())


@contextmanager
def fixture_server():
    with tempfile.TemporaryDirectory(prefix='cookie-fixture-') as tmp:
        cert, key = Path(tmp)/'cert.pem', Path(tmp)/'key.pem'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                        '-keyout', str(key), '-out', str(cert), '-subj', '/CN=localhost'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.session_active = True
        server.events = []
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain(cert, key)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try: yield server, f'https://localhost:{server.server_port}'
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)
