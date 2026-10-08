"""Owned loopback integration tests; no external URLs, keys or provider calls."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PNG = Path("fixtures/pixel.png").read_bytes()
JPEG = Path("fixtures/pixel.jpg").read_bytes()
BODY_PREFIX_SENT = threading.Event()

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *args): pass
    def do_GET(self):
        route = self.path
        status = 404 if route == "/missing" else 302 if route == "/redirect" else 200
        body = b"<html>login</html>" if route in ("/html", "/forged") else b"" if route == "/empty" else PNG
        if route in ("/jpeg", "/mismatch"): body = JPEG
        if route in ("/large", "/unknown-large"): body = PNG + b"x" * 2048
        self.send_response(status)
        if route != "/missing_mime":
            self.send_header("Content-Type", "text/html" if route == "/html" else "image/jpeg" if route == "/jpeg" else "image/png")
        if route == "/redirect": self.send_header("Location", "/ok")
        if route != "/unknown-large": self.send_header("Content-Length", str(len(body) + (20 if route == "/truncated" else 0)))
        self.send_header("Connection", "close"); self.end_headers()
        try:
            if route == "/slow":
                self.wfile.write(body[:8]); self.wfile.flush(); BODY_PREFIX_SENT.set(); time.sleep(0.8); self.wfile.write(body[8:])
            else: self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError): pass
        self.close_connection = True

def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    records = []
    try:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cases = [("ok", "/ok", [], True), ("jpeg", "/jpeg", [], True), ("http404", "/missing", [], False),
                ("html", "/html", [], False), ("forged_png_mime", "/forged", [], False),
                ("missing_mime", "/missing_mime", [], False), ("mismatched_signature", "/mismatch", [], False),
                ("empty", "/empty", [], False), ("declared_oversize", "/large", ["--max-bytes", "100"], False),
                ("unknown_length_oversize", "/unknown-large", ["--max-bytes", "100"], False),
                ("truncated", "/truncated", [], False), ("body_timeout", "/slow", ["--timeout-ms", "300"], False),
                ("redirect", "/redirect", [], False), ("existing_file", "/ok", [], False),
                ("http_without_opt_in", "/ok", [], False)]
            for name, route, options, success in cases:
                destination = root / (name + ".png")
                if name == "existing_file": destination.write_bytes(b"keep me")
                command = ["dotnet", "run", "--no-build", "-c", "Release", "--",
                    f"http://127.0.0.1:{server.server_port}{route}", str(destination), *options]
                if name != "http_without_opt_in": command.append("--allow-loopback")
                result = subprocess.run(command, capture_output=True, text=True, timeout=10)
                assert (result.returncode == 0) == success, (name, result.stdout, result.stderr)
                if success:
                    assert destination.read_bytes() == (JPEG if name == "jpeg" else PNG), name + " byte oracle"
                elif name == "existing_file": assert destination.read_bytes() == b"keep me"
                else: assert not destination.exists(), name + " left a published file"
                assert not list(root.glob("*.part")), name + " left temporary bytes"
                if name == "body_timeout":
                    assert BODY_PREFIX_SENT.is_set(), "Timeout did not reach the body stage"
                    assert "CanceledException" in result.stderr, result.stderr
                records.append({"case": name, "passed": True, "exit_code": result.returncode,
                    "stdout": result.stdout.strip(), "error_type": result.stderr.split(":", 1)[0].strip(),
                    "saved_sha256": hashlib.sha256(destination.read_bytes()).hexdigest() if success else None})
    finally:
        server.shutdown(); server.server_close(); worker.join()
    print(json.dumps({"fixture_bytes": len(PNG), "fixture_sha256": hashlib.sha256(PNG).hexdigest(),
        "jpeg_fixture_bytes": len(JPEG), "jpeg_fixture_sha256": hashlib.sha256(JPEG).hexdigest(),
        "cases": records}, indent=2))

if __name__ == "__main__": main()
