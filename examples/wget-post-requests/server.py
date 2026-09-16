"""Local target for the wget cases: echoes the request, and provides redirect, error, auth, cookie, flaky and slow endpoints."""
import base64, http.server, json, sys, time, urllib.parse

FLAKY_FAILS = {"left": 2}

class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.command, self.path)); sys.stderr.flush()

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _send(self, code, body, ctype="application/json", extra=()):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data)))
        for k, v in extra: self.send_header(k, v)
        self.end_headers(); self.wfile.write(data)

    def _echo(self):
        body = self._req_body
        info = {"method": self.command, "path": self.path, "content_type": self.headers.get("Content-Type"),
                "content_length": self.headers.get("Content-Length"), "authorization": self.headers.get("Authorization"),
                "cookie": self.headers.get("Cookie"), "user_agent": self.headers.get("User-Agent"), "body": body.decode("utf-8", "replace")}
        if info["content_type"] == "application/x-www-form-urlencoded":
            info["form"] = urllib.parse.parse_qs(info["body"])
        self._send(200, json.dumps(info, indent=1) + "\n")

    def _route(self):
        self._req_body = self._body()   # always drain the body so keep-alive connections stay in sync
        p = self.path.split("?")[0]
        if p == "/echo": return self._echo()
        if p.startswith("/redirect"):
            code = int(p[len("/redirect"):]); return self._send(code, "", "text/plain", [("Location", "/echo")])
        if p == "/error400": return self._send(400, '{"error": "field user is required"}\n')
        if p == "/flaky":
            if FLAKY_FAILS["left"] > 0:
                FLAKY_FAILS["left"] -= 1; return self._send(503, "try again\n", "text/plain")
            return self._echo()
        if p == "/slow":
            time.sleep(3); return self._send(200, "late\n", "text/plain")
        if p == "/auth":
            a = self.headers.get("Authorization", "")
            if a == "Basic " + base64.b64encode(b"user:pass").decode(): return self._echo()
            return self._send(401, "auth required\n", "text/plain", [("WWW-Authenticate", 'Basic realm="test"')])
        if p == "/login":
            form = urllib.parse.parse_qs(self._req_body.decode())
            if form.get("user") == ["foo"] and form.get("password") == ["bar"]:
                return self._send(200, "logged in\n", "text/plain", [("Set-Cookie", "session=abc123; Path=/")])
            return self._send(403, "bad credentials\n", "text/plain")
        if p == "/me":
            if "session=abc123" in (self.headers.get("Cookie") or ""): return self._send(200, "hello foo\n", "text/plain")
            return self._send(401, "no session\n", "text/plain")
        self._send(404, "not found\n", "text/plain")

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _route

http.server.ThreadingHTTPServer(("127.0.0.1", 8000), H).serve_forever()
