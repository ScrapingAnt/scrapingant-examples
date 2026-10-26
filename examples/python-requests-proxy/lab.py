"""Local lab for the Python Requests proxy guide.

Starts an echo origin on 127.0.0.1:8000, proxy.py instances on 8899 (Basic auth
lab / p@ss#w0rd), 8901 and 8902, a SOCKS5 proxy (pproxy) with auth on 1080, and
leaves 8903 closed as a dead proxy. Then runs every script in cases/ and saves
its output to expected_output/<case>.txt. Exits non-zero if a case fails.
"""
import contextlib, http.server, json, os, pathlib, socket, subprocess, sys, threading, time

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "expected_output"
PY = sys.executable
# proxy env vars from the shell would change what the cases measure
ENV = {k: v for k, v in os.environ.items() if k.lower() not in ("http_proxy", "https_proxy", "all_proxy", "no_proxy")}
ENV["PYTHONPATH"] = str(ROOT)


class Origin(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({
            "path": self.path,
            "via": self.headers.get("X-Lab-Proxy"),
            "authorization_sent_to_site": self.headers.get("Authorization") is not None,
        }) + "\n"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *a):
        pass


def wait_port(port, child=None):
    for _ in range(200):
        if child is not None and child.poll() is not None:
            raise RuntimeError(f"process on {port} exited")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError(port)


@contextlib.contextmanager
def lab():
    OUT.mkdir(exist_ok=True)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8000), Origin)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    children = []

    def start(port, args, log):
        child = subprocess.Popen(args, cwd=ROOT, stdout=open(OUT / log, "w"), stderr=subprocess.STDOUT, start_new_session=True, env=ENV)
        children.append(child)
        wait_port(port, child)

    proxy = [PY, "-m", "proxy", "--hostname", "127.0.0.1", "--num-workers", "1", "--num-acceptors", "1", "--log-level", "INFO"]
    try:
        start(8899, proxy + ["--port", "8899", "--basic-auth", "lab:p@ss#w0rd", "--plugins", "lab_plugins.AuthProxy"], "proxy-8899.log")
        start(8901, proxy + ["--port", "8901", "--plugins", "lab_plugins.ProxyA"], "proxy-8901.log")
        start(8902, proxy + ["--port", "8902", "--plugins", "lab_plugins.ProxyB"], "proxy-8902.log")
        start(1080, [PY, "-m", "pproxy", "-l", "socks5://127.0.0.1:1080#lab:secret"], "socks-1080.log")
        yield
    finally:
        for c in children:
            c.terminate()
        for c in children:
            c.wait(timeout=10)
        srv.shutdown()


def main():
    only = sys.argv[1:]
    failed = []
    with lab():
        for case in sorted((ROOT / "cases").glob("*.py")):
            if only and case.stem not in only:
                continue
            if case.stem.startswith("09") and not os.environ.get("SCRAPINGANT_API_KEY"):
                print(f"--- {case.stem}: skipped (SCRAPINGANT_API_KEY not set)")
                continue
            r = subprocess.run([PY, str(case)], cwd=ROOT, capture_output=True, text=True, timeout=120, env=ENV)
            text = r.stdout + r.stderr + f"exit={r.returncode}\n"
            (OUT / f"{case.stem}.txt").write_text(text)
            print(f"--- {case.stem}\n{text}", end="")
            if r.returncode != 0:
                failed.append(case.stem)
    if failed:
        print("FAILED:", failed)
        sys.exit(1)


if __name__ == "__main__":
    main()
