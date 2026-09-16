#!/usr/bin/env bash
# The GnuTLS-build counterpart of cases 00/01/02/03/03b/04b/07, run inside debian:bookworm-slim (Debian's wget links GnuTLS).
# Writes expected_output/gnutls/*.txt. Needs Docker; not part of ./run.sh.
set -uo pipefail
cd "$(dirname "$0")"; mkdir -p expected_output/gnutls
docker run --rm -v "$PWD:/w" -w /w debian:bookworm-slim bash -c '
set -uo pipefail; export LC_ALL=C
apt-get update -qq > /dev/null && apt-get install -y -qq wget openssl python3 ca-certificates > /dev/null 2>&1
mkdir -p /tmp/certs && openssl req -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost" -keyout /tmp/certs/localhost-key.pem -out /tmp/certs/localhost.pem 2>/dev/null
cat > /tmp/server.py <<PY
import http.server, ssl
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain("/tmp/certs/localhost.pem", "/tmp/certs/localhost-key.pem")
srv = http.server.HTTPServer(("127.0.0.1", 8443), lambda *a: http.server.SimpleHTTPRequestHandler(*a, directory="/w/fixtures"))
srv.socket = ctx.wrap_socket(srv.socket, server_side=True); srv.serve_forever()
PY
python3 /tmp/server.py 2>/dev/null & sleep 1
U=https://localhost:8443/index.html
rec() { { echo "\$ $2"; bash -c "$3" 2>&1; echo "exit=$?"; } > "expected_output/gnutls/$1.txt"; }
{ cat /etc/os-release | grep PRETTY_NAME; wget --version | head -1; wget --version | grep -o -- "+ssl/[a-z]*"; echo "wget links: $(ldd "$(command -v wget)" | grep -oE "[^ ]*(libssl|libgnutls)[^ ]*" | tr "\n" " ")"; } > expected_output/gnutls/00_versions.txt
rec 01_default "wget -4 -nv -O- $U" "wget -4 -nv -O- $U"
rec 02_no_check_certificate "wget -4 -nv -O- --no-check-certificate $U" "wget -4 -nv -O- --no-check-certificate $U"
rec 03_ca_certificate "wget -4 -nv -O- --ca-certificate=/tmp/certs/localhost.pem $U" "wget -4 -nv -O- --ca-certificate=/tmp/certs/localhost.pem $U"
P=https://scrapingant.github.io/scrapingant-examples/fixtures/dynamic-delayed.html
rec 03b_ca_certificate_public "wget -4 -nv -O /dev/null --ca-certificate=/tmp/certs/localhost.pem $P" "wget -4 -nv -O /dev/null --ca-certificate=/tmp/certs/localhost.pem $P"
mkdir -p /tmp/cadir && cp /tmp/certs/localhost.pem /tmp/cadir/ && openssl rehash /tmp/cadir > /dev/null 2>&1
rec 04b_ca_directory_public "wget -4 -nv -O /dev/null --ca-directory=/tmp/cadir $P" "wget -4 -nv -O /dev/null --ca-directory=/tmp/cadir $P"
rec 07_ssl_cert_file "SSL_CERT_FILE=/tmp/certs/localhost.pem wget -4 -nv -O- $U" "SSL_CERT_FILE=/tmp/certs/localhost.pem wget -4 -nv -O- $U"
sed -i -E "s/^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} /<time> /" expected_output/gnutls/*.txt
'
for f in expected_output/gnutls/*.txt; do echo "=== $f"; cat "$f"; done
