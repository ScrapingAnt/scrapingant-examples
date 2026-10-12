"""Owned loopback fixture server. Deliberate mutations exercise failure boundaries."""
from contextlib import AbstractContextManager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlsplit

FIXTURES = Path(__file__).parent / "fixtures"


class FixtureServer(AbstractContextManager):
    def __init__(self, port=0):
        self.mode = "baseline"
        self.requests = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                owner.requests.append(self.path)
                parsed = urlsplit(self.path)
                page = parse_qs(parsed.query).get("page", ["1"])[0]
                if parsed.path != "/careers/roles" or page not in ("1", "2"):
                    self.send_error(404)
                    return
                if owner.mode == "http_fail" and page == "2":
                    self.send_error(503)
                    return
                if owner.mode == "redirect" and page == "1":
                    self.send_response(302)
                    self.send_header("Location", "https://unapproved.invalid/careers/roles?page=1")
                    self.end_headers()
                    return
                filename = (f"refresh-{page}.html" if owner.mode in ("refresh", "http_fail")
                            else f"page-{page}.html")
                if owner.mode == "empty":
                    filename = "empty.html"
                if owner.mode == "denied" and page == "2":
                    filename = "denied.html"
                body = (FIXTURES / filename).read_text()
                replacements = {
                    "hostile_next": ("/careers/roles?page=2", "https://unapproved.invalid/careers/roles?page=2"),
                    "wrong_path": ("/careers/roles?page=2", "/admin?page=2"),
                    "wrong_page": ("/careers/roles?page=2", "/careers/roles?page=3"),
                    "changed_filter": ("/careers/roles?page=2", "/careers/roles?page=2&amp;department=other"),
                    "duplicate_query": ("/careers/roles?page=2", "/careers/roles?page=2&amp;page=2"),
                    "fragment_next": ("/careers/roles?page=2", "/careers/roles?page=2#hidden"),
                    "loop": ("/careers/roles?page=2", "/careers/roles?page=1"),
                    "missing_next": ('rel="next"', 'rel="other"'),
                }
                if page == "1" and owner.mode in replacements:
                    body = body.replace(*replacements[owner.mode])
                if page == "2" and owner.mode == "conflict":
                    body = body.replace("Platform Engineer", "Different Engineer")
                if page == "2" and owner.mode == "missing_location":
                    body = body.replace('<span class="job-location">Dublin, Ireland</span>', "")
                if page == "2" and owner.mode == "source_mismatch":
                    body = body.replace("/careers/jobs/NS-003", "/careers/jobs/NS-999")
                if page == "2" and owner.mode == "application_external":
                    body = body.replace("/careers/apply/NS-003", "https://unapproved.invalid/apply/NS-003")
                if page == "2" and owner.mode == "invalid_date":
                    body = body.replace("2026-10-05", "2026-02-30")
                if page == "2" and owner.mode == "changed_total":
                    body = body.replace('data-total-pages="2"', 'data-total-pages="3"')
                if owner.mode == "empty_unconfirmed":
                    body = (FIXTURES / "empty.html").read_text().replace('data-status="empty"', 'data-status="open"')
                if owner.mode == "not_html":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"jobs": []}')
                    return
                if owner.mode == "oversized":
                    body = "x" * 1_000_001
                if owner.mode == "duplicate_envelope":
                    body += body
                data = body.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.origin = f"http://127.0.0.1:{self.httpd.server_port}"
        self.url = self.origin + "/careers/roles?page=1"
        self.thread = Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join()


if __name__ == "__main__":
    # Optional standalone server for the article's manual CLI command.
    import argparse
    import signal
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8873)
    args = parser.parse_args()
    with FixtureServer(args.port) as server:
        print(server.url, flush=True)
        signal.pause()
