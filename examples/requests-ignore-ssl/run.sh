#!/usr/bin/env bash
# Every recipe from the article, run against a local HTTPS server with a self-signed
# certificate (SAN: DNS:localhost only) started here on 127.0.0.1:8443.
set -uo pipefail
cd "$(dirname "$0")"; rm -rf expected_output; mkdir -p expected_output certs; status=0
if [ ! -f certs/localhost.pem ]; then
  openssl req -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost" -keyout certs/localhost-key.pem -out certs/localhost.pem >/dev/null 2>&1
fi
cat "$(python -m certifi)" certs/localhost.pem > certs/bundle.pem
python server.py 2> server.log & SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT
for i in $(seq 1 20); do python -c "import socket; socket.create_connection(('127.0.0.1', 8443), 1)" 2>/dev/null && break; sleep 0.5; done

{ echo "python: $(python --version 2>&1)"; python -c "import requests,urllib3,certifi,ssl; print(f'requests: {requests.__version__}\nurllib3: {urllib3.__version__}\ncertifi: {certifi.__version__}\n{ssl.OPENSSL_VERSION}')"; echo "openssl cli: $(openssl version)"; } > expected_output/00_versions.txt
for script in [0-9][0-9]_*.py; do
  name="${script%.py}"
  { echo "\$ python $script"; python "$script" 2>&1; echo "exit=$?"; } > "expected_output/$name.txt"
done
for f in expected_output/*.txt; do echo "=== $f"; cat "$f"; done

g() { grep -q -- "$2" "expected_output/$1"*.txt || { echo "FAILED: $1 missing '$2'"; status=1; }; }
g 01 "CERTIFICATE_VERIFY_FAILED"; g 02 "verify=False): 200"; g 02 "# again: 200"; g 02 "no verify=: requests.exceptions.SSLError"; g 03 ": 200"
test "$(grep -c '^InsecureRequestWarning' expected_output/02_*.txt)" = 2 || { echo "FAILED: 02 expected two warnings"; status=1; }
g 04 "s.get(URL): 200"; g 04 "verify=True): requests.exceptions.SSLError"
g 05 "requests.get(URL, verify='certs/localhost.pem'): 200"; g 05 "IP address mismatch"; g 05 "replaces certifi: requests.exceptions.SSLError"
g 12 "verify='certs/bundle.pem'): 200"; test "$(grep -c ': 200' expected_output/12_*.txt)" = 2 || { echo "FAILED: 12"; status=1; }
g 06 "REQUESTS_CA_BUNDLE=certs/localhost.pem python env_check.py"; g 06 "requests.get(URL): 200"; g 06 "trust_env=False; s.get(URL): requests.exceptions.SSLError"; g 06 "Could not find a suitable TLS CA certificate bundle"
g 07 "not SSLContext"; g 08 "s.get(URL): 200"; g 08 "s2.get(IP_URL): requests.exceptions.SSLError"; g 08 "s3.get(IP_URL): 200"; g 08 "s3.get(URL) (localhost not mounted -> still verified): requests.exceptions.SSLError"
g 09 "_create_unverified_context()): 200"; g 10 "CERT_NONE'): 200"; g 10 "ca_certs=CA): 200"; g 11 "verify=True: 200"
grep -q "^InsecureRequestWarning" expected_output/03_*.txt && { echo "FAILED: 03 still warns"; status=1; }
echo "status=$status"; exit $status
