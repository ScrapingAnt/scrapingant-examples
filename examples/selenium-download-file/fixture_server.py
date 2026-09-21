"""Loopback-only HTTP fixture server with explicit download headers."""
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import time

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/selenium-download-file"
CASES = {
    "csv": ("report.csv", "text/csv"),
    "slow": ("payload.bin", "application/octet-stream"),
    "pdf": ("sample.pdf", "application/pdf"),
}


def expected(case):
    name, _ = CASES[case]
    payload = (FIXTURES / name).read_bytes()
    return name, len(payload), hashlib.sha256(payload).hexdigest()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        route = self.path.split("?", 1)[0]
        if route == "/":
            body = (FIXTURES / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        case = route.removeprefix("/download/")
        if case not in CASES and case != "interrupted":
            self.send_error(404)
            return
        name, mime = CASES["slow" if case == "interrupted" else case]
        body = (FIXTURES / name).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            if case == "interrupted":
                self.wfile.write(body[:1024])
                self.wfile.flush()
                self.close_connection = True
            elif case == "slow":
                for start in range(0, len(body), 4096):
                    self.wfile.write(body[start:start + 4096])
                    self.wfile.flush()
                    time.sleep(0.1)
            else:
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass


@contextmanager
def fixture_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
