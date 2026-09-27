"""Self-authored local HTTP catalog. Every value and identity is synthetic."""
from contextlib import AbstractContextManager
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from urllib.parse import urlsplit

# Fixture data deliberately does not import the independent extraction oracle.
SKUS = ("BK-101", "PN-202", "NB-303", "BG-404")
PRICES = {
    (True, "EUR"): (1499, 799, 2199, 4299),
    (True, "USD"): (1699, 899, 2399, 4699),
    (False, "EUR"): (1999, 1099, 2899, 5699),
    (False, "USD"): (2199, 1199, 3199, 6199),
}
SYNTHETIC_SESSION = "fixture-member-only"


class CatalogFixture(AbstractContextManager):
    def __enter__(self):
        fixture = self
        self.revoked = False

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass  # Never print raw headers or cookie values.

            def send_json(self, payload, *, status=200, headers=()):
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                for name, value in headers:
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path = urlsplit(self.path).path
                if path == "/login":
                    self.send_json({"redirect": True}, status=302, headers=(
                        ("Location", "/configure"),
                        ("Set-Cookie", f"sid={SYNTHETIC_SESSION}; Path=/; HttpOnly; SameSite=Lax"),
                    ))
                elif path == "/configure":
                    self.send_json({"configured": True}, headers=(
                        ("Set-Cookie", "region=EUR; Path=/catalog/eu; Max-Age=3600"),
                        ("Set-Cookie", "region=USD; Path=/catalog/us; Max-Age=3600"),
                    ))
                elif path in ("/catalog/eu/products", "/catalog/us/products"):
                    header = self.headers.get("Cookie", "")
                    cookies = SimpleCookie()
                    cookies.load(header)
                    sid = cookies.get("sid")
                    region = cookies.get("region")
                    known_sid = sid is not None and sid.value == SYNTHETIC_SESSION
                    member = known_sid and not fixture.revoked
                    currency = "EUR" if region and region.value == "EUR" else "USD"
                    self.send_json({
                        "records": [dict(sku=sku, currency=currency, price_minor=price)
                                    for sku, price in zip(SKUS, PRICES[(member, currency)])],
                        "wire": {
                            "session_cookie_received": sid is not None,
                            "active_member": member,
                            "region_cookie_count": sum(part.strip().startswith("region=") for part in header.split(";")),
                            "region_is_eur": bool(region and region.value == "EUR"),
                            "region_is_usd": bool(region and region.value == "USD"),
                            "selected_currency": currency,
                        },
                    })
                else:
                    self.send_json({"error": "unknown local fixture route"}, status=404)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        return self

    def revoke(self):
        """Simulate server-side invalidation while retaining the client's cookie."""
        self.revoked = True

    def __exit__(self, *_args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
