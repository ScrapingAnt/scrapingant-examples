"""HTTPS server on 127.0.0.1:8443 with a self-signed certificate (SAN: DNS:localhost only)."""
import http.server, ssl, sys
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain("certs/localhost.pem", "certs/localhost-key.pem")
srv = http.server.HTTPServer(("127.0.0.1", 8443), lambda *a: http.server.SimpleHTTPRequestHandler(*a, directory="fixtures"))
srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
print("listening on https://localhost:8443", file=sys.stderr, flush=True)
srv.serve_forever()
