"""Two HTTPS servers, each on IPv4 and IPv6 loopback so `localhost` resolves without a refused first attempt:
   8443 self-signed certificate (SAN localhost), 8444 expired certificate."""
import http.server, socket, ssl, sys, threading

class V6Server(http.server.ThreadingHTTPServer):
    address_family = socket.AF_INET6

def serve(host, port, cert, key):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain(cert, key)
    cls = V6Server if ":" in host else http.server.ThreadingHTTPServer
    srv = cls((host, port), lambda *a: http.server.SimpleHTTPRequestHandler(*a, directory="fixtures"))
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    print(f"listening on {host}:{port}", file=sys.stderr, flush=True); srv.serve_forever()

for host in ("127.0.0.1", "::1"):
    threading.Thread(target=serve, args=(host, 8444, "certs/expired.pem", "certs/expired-key.pem"), daemon=True).start()
    threading.Thread(target=serve, args=(host, 8443, "certs/localhost.pem", "certs/localhost-key.pem"), daemon=True).start()
threading.Event().wait()
