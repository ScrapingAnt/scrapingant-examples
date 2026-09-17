#!/usr/bin/env bash
# Every snippet and measurement from the article, run against the local hypercorn server started here
# (plain HTTP on 127.0.0.1:8080, TLS with ALPN h2 on localhost:8443 with a self-signed certificate).
set -uo pipefail
export LC_ALL=C LANG=C
cd "$(dirname "$0")"; mkdir -p expected_output certs generated; rm -f expected_output/[0-9]*.txt; status=0
if [ ! -f certs/localhost.pem ]; then
  openssl req -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:::1" -keyout certs/localhost-key.pem -out certs/localhost.pem >/dev/null 2>&1
fi
python server.py 2> server.log & SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT
for i in $(seq 1 40); do python -c "import socket; socket.create_connection(('127.0.0.1', 8443), 1)" 2>/dev/null && break; sleep 0.5; done

{ echo "python: $(python --version 2>&1)"; python -c "
from importlib.metadata import version; import ssl
for p in ('requests','urllib3','httpx','httpcore','h2','anyio','hypercorn'): print(p, version(p))
print(ssl.OPENSSL_VERSION)"; echo "openssl cli: $(openssl version)"; } > expected_output/00_versions.txt
for script in [0-9][0-9]_*.py; do
  name="${script%.py}"; echo "== $name"
  { echo "\$ python $script"; python "$script" 2>&1; echo "exit=$?"; } > "expected_output/$name.txt"
done
for f in expected_output/[0-9]*.txt; do echo "=== $f"; cat "$f"; done
g() { grep -qF -- "$2" "expected_output/$1"*.txt || { echo "FAILED: $1 missing '$2'"; status=1; }; }
for n in 01 02 03 03b 04 05 06 07 08 09 11; do g $n "exit=0"; done
g 01 "DeprecationWarning"; g 01 "httpx    params={'a': None, 'b': 1}"; g 02 "httpx.ReadTimeout"; g 02 "history: [302, 302]"
g 03 "httpx.Client x N"; g 03 "verify=ctx"; g 03b "certifi.where"; g 08 "cert=... is deprecated"; g 04 "pool is full"; g 04 "AsyncClient"; g 05 "http_version = HTTP/2"; g 05 "h2"; g 06 "peak RSS"
g 07 "httpx.HTTPStatusError"; g 07 "server saw 4 requests"; g 07 "server saw 1 requests"; g 08 "TypeError"; g 09 "httpx 1.0"
echo "status=$status"; exit $status
