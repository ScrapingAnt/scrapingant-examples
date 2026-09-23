"""Local-only integration fixture. Provider TEST keys are public and intentionally non-secret."""
import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
import requests

GOOGLE_SITE = '6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI'
GOOGLE_SECRET = '6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe'
TURNSTILE_SITE = '1x00000000000000000000AA'
TURNSTILE_SECRETS = {
    'pass': '1x0000000000000000000000000000000AA',
    'reject': '2x0000000000000000000000000000000AA',
    'duplicate': '3x0000000000000000000000000000000AA',
}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, status, payload, mime):
        data = payload.encode()
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        provider = query.get('provider', ['google'])[0]
        mode = query.get('mode', ['pass'])[0]
        if provider not in ('google', 'turnstile') or mode not in TURNSTILE_SECRETS:
            self.send(400, 'Invalid fixture parameters', 'text/plain'); return
        script = 'https://www.google.com/recaptcha/api.js' if provider == 'google' else 'https://challenges.cloudflare.com/turnstile/v0/api.js'
        css = 'g-recaptcha' if provider == 'google' else 'cf-turnstile'
        sitekey = GOOGLE_SITE if provider == 'google' else TURNSTILE_SITE
        html = f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>CAPTCHA test-key fixture</title>
<h1>CAPTCHA integration fixture — TEST KEYS ONLY</h1>
<p>Success here demonstrates wiring, not a production CAPTCHA bypass.</p>
<form id="fixture" method="post" action="/verify?provider={provider}&mode={mode}">
<div class="{css}" data-sitekey="{sitekey}"></div><button id="submit" type="submit">Verify on server</button></form>
<script src="{script}" async defer></script></html>'''
        self.send(200, html, 'text/html; charset=utf-8')

    def do_POST(self):
        query = parse_qs(urlparse(self.path).query)
        provider = query.get('provider', ['google'])[0]
        mode = query.get('mode', ['pass'])[0]
        if urlparse(self.path).path != '/verify' or provider not in ('google','turnstile') or mode not in TURNSTILE_SECRETS:
            self.send(400, '{}', 'application/json'); return
        body = parse_qs(self.rfile.read(min(int(self.headers.get('Content-Length',0)),8192)).decode())
        token = body.get('g-recaptcha-response' if provider == 'google' else 'cf-turnstile-response', [''])[0]
        result = {'test_mode': True, 'provider': provider, 'mode': mode, 'token_length': len(token)}
        if not token:
            result.update(accepted=False, verification_called=False, error_codes=['missing-token'])
        else:
            endpoint = 'https://www.google.com/recaptcha/api/siteverify' if provider == 'google' else 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
            secret = GOOGLE_SECRET if provider == 'google' else TURNSTILE_SECRETS[mode]
            try:
                response = requests.post(endpoint, data={'secret':secret,'response':token}, timeout=30)
                response.raise_for_status()
                verification = response.json()
                result.update(accepted=verification.get('success') is True, verification_called=True,
                              provider_http_status=response.status_code, verification=verification)
            except (requests.RequestException, ValueError) as exc:
                result.update(accepted=False, verification_called=True, transport_error=type(exc).__name__)
        self.send(200 if result['accepted'] else 403, json.dumps(result), 'application/json')

@contextmanager
def serve():
    server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
    worker = threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown();server.server_close();worker.join()
