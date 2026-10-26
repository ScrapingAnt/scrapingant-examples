"""Local lab for the IP restrictions guide.

Origin on 127.0.0.1:8000 enforces a per-client limit: 5 requests per 10-second
window. Over the limit it answers 429 with Retry-After. A client that keeps
going after 3 refused requests is banned (403) for the rest of the run.
The origin can't see real exit IPs on loopback, so it identifies the client by
the X-Lab-Proxy header the lab proxies add (8901, 8902), or "direct" without one.
This simulates two exit IPs; it is disclosed in the article.
"""
import http.server, json, os, pathlib, socket, subprocess, sys, threading, time

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "expected_output"
PY = sys.executable
ENV = {k: v for k, v in os.environ.items() if k.lower() not in ("http_proxy", "https_proxy", "all_proxy", "no_proxy")}
ENV["PYTHONPATH"] = str(ROOT)
LIMIT, WINDOW, BAN_AFTER = 5, 10.0, 3
state, lock = {}, threading.Lock()


class Origin(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/reset":
            with lock:
                state.clear()
            return self.reply(200, {"reset": True})
        client = self.headers.get("X-Lab-Proxy") or "direct"
        now = time.monotonic()
        with lock:
            s = state.setdefault(client, {"hits": [], "refused": 0, "banned": False})
            s["hits"] = [t for t in s["hits"] if now - t < WINDOW]
            if s["banned"]:
                return self.reply(403, {"client": client, "error": "banned"})
            if len(s["hits"]) >= LIMIT:
                s["refused"] += 1
                if s["refused"] > BAN_AFTER:
                    s["banned"] = True
                    return self.reply(403, {"client": client, "error": "banned"})
                retry = max(1, round(WINDOW - (now - s["hits"][0])))
                return self.reply(429, {"client": client, "error": "rate limited"}, {"Retry-After": str(retry)})
            s["hits"].append(now)
            s["refused"] = 0
        self.reply(200, {"client": client, "path": self.path})

    def reply(self, code, body, headers=None):
        data = (json.dumps(body) + "\n").encode()
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def wait_port(port):
    for _ in range(200):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError(port)


def main():
    only = sys.argv[1:]
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8000), Origin)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    proxy = [PY, "-m", "proxy", "--hostname", "127.0.0.1", "--num-workers", "1", "--num-acceptors", "1"]
    kids = [subprocess.Popen(proxy + ["--port", str(p), "--plugins", f"lab_plugins.{n}"], cwd=ROOT, env=ENV,
                             stdout=open(OUT / f"proxy-{p}.log", "w"), stderr=subprocess.STDOUT)
            for p, n in [(8901, "ProxyA"), (8902, "ProxyB")]]
    for p in (8901, 8902):
        wait_port(p)
    failed = []
    try:
        for case in sorted((ROOT / "cases").glob("*.py")):
            if only and case.stem not in only:
                continue
            if case.stem.startswith("05") and not os.environ.get("SCRAPINGANT_API_KEY"):
                print(f"--- {case.stem}: skipped (SCRAPINGANT_API_KEY not set)")
                continue
            with lock:
                state.clear()
            r = subprocess.run([PY, str(case)], cwd=ROOT, capture_output=True, text=True, timeout=180, env={**ENV, **({"SCRAPINGANT_API_KEY": os.environ["SCRAPINGANT_API_KEY"]} if os.environ.get("SCRAPINGANT_API_KEY") else {})})
            text = r.stdout + r.stderr
            (OUT / f"{case.stem}.txt").write_text(text)
            print(f"--- {case.stem}\n{text}exit={r.returncode}", flush=True)
            if r.returncode:
                failed.append(case.stem)
    finally:
        for k in kids:
            k.terminate()
        srv.shutdown()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
