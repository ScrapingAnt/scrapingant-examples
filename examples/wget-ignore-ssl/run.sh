#!/usr/bin/env bash
# Every wget command from the article, run against two local HTTPS servers started here:
#   https://localhost:8443  self-signed certificate (SAN localhost)
#   https://localhost:8444  expired certificate
set -uo pipefail
export LC_ALL=C LANG=C
cd "$(dirname "$0")"; rm -rf expected_output; mkdir -p expected_output; status=0
python3 gen_certs.py > /dev/null
python3 server.py 2> server.log & SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT
for i in $(seq 1 20); do python3 -c "import socket; socket.create_connection(('127.0.0.1', 8444), 1)" 2>/dev/null && break; sleep 0.5; done
U=https://localhost:8443/index.html
rec() { { echo "\$ $2"; bash -c "$3" 2>&1; echo "exit=$?"; } > "expected_output/$1.txt"; }
{ wget --version | head -1; wget --version | grep -o -- '+ssl/[a-z]*'; echo "openssl cli: $(openssl version)"; echo "curl: $(curl --version | head -1)"; echo "python3: $(python3 --version 2>&1)"; } > expected_output/00_versions.txt
BACKEND=$(wget --version | grep -o -- '+ssl/[a-z]*' | cut -d/ -f2)

rec 01_default            "wget -nv -O- $U"                                                                    "wget -nv -O- $U"
rec 02_no_check_certificate "wget -nv -O- --no-check-certificate $U"                                           "wget -nv -O- --no-check-certificate $U"
rec 03_ca_certificate     "wget -nv -O- --ca-certificate=certs/localhost.pem $U"                                "wget -nv -O- --ca-certificate=certs/localhost.pem $U"
mkdir -p cadir && cp certs/localhost.pem cadir/ && openssl rehash cadir > /dev/null 2>&1
rec 04_ca_directory       "openssl rehash cadir; ls cadir; wget -nv -O- --ca-directory=cadir $U"                  "ls cadir; wget -nv -O- --ca-directory=cadir $U"
rec 05_ip_mismatch        "wget -nv -O- --ca-certificate=certs/localhost.pem https://127.0.0.1:8443/index.html" "wget -nv -O- --ca-certificate=certs/localhost.pem https://127.0.0.1:8443/index.html"
rec 06_expired            "wget -nv -O- --ca-certificate=certs/expired.pem https://localhost:8444/index.html"    "wget -nv -O- --ca-certificate=certs/expired.pem https://localhost:8444/index.html"
rec 07_ssl_cert_file      "SSL_CERT_FILE=certs/localhost.pem wget -nv -O- $U   # wget built with +ssl/$BACKEND"   "SSL_CERT_FILE=certs/localhost.pem wget -nv -O- $U"
rec 08_wgetrc             "printf 'check_certificate = off\\n' > wgetrc.test; WGETRC=wgetrc.test wget -nv -O- $U"   "printf 'check_certificate = off\\n' > wgetrc.test; WGETRC=wgetrc.test wget -nv -O- $U"
rec 09_execute_option     "wget -nv -O- -e check_certificate=off $U"                                             "wget -nv -O- -e check_certificate=off $U"
PIN=$(openssl x509 -in certs/localhost.pem -pubkey -noout | openssl pkey -pubin -outform der | openssl dgst -sha256 -binary | base64)
rec 10_pinnedpubkey_ok    "PIN=\$(openssl x509 -in certs/localhost.pem -pubkey -noout | openssl pkey -pubin -outform der | openssl dgst -sha256 -binary | base64); wget -nv -O- --no-check-certificate --pinnedpubkey=\"sha256//\$PIN\" $U"   "wget -nv -O- --no-check-certificate --pinnedpubkey=\"sha256//$PIN\" $U"
rec 11_pinnedpubkey_wrong "wget -nv -O- --no-check-certificate --pinnedpubkey=\"sha256//AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=\" $U"   "wget -nv -O- --no-check-certificate --pinnedpubkey=\"sha256//AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=\" $U"
rec 12_pinnedpubkey_with_verify "wget -nv -O- --pinnedpubkey=\"sha256//\$PIN\" $U   # no --no-check-certificate"   "wget -nv -O- --pinnedpubkey=\"sha256//$PIN\" $U"
rec 13_secure_protocol    "wget -nv -O- --secure-protocol=TLSv1_2 --ca-certificate=certs/localhost.pem $U"         "wget -nv -O- --secure-protocol=TLSv1_2 --ca-certificate=certs/localhost.pem $U"
rec 14_curl_equivalent    "curl -sS $U; echo; curl -sS -k $U; curl -sS --cacert certs/localhost.pem $U"           "curl -sS $U; echo; curl -sS -k $U; curl -sS --cacert certs/localhost.pem $U"
rm -rf cadir wgetrc.test
sed -i.bak -E 's/^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} /<time> /; s/issued by .CN=localhost./issued by `CN=localhost'"'"'/' expected_output/*.txt; rm -f expected_output/*.bak
for f in expected_output/*.txt; do echo "=== $f"; cat "$f"; done
g() { grep -q -- "$2" "expected_output/$1"*.txt || { echo "FAILED: $1 missing '$2'"; status=1; }; }
g 01 "cannot verify localhost's certificate"; g 01 "exit=5"; g 02 "WARNING"; g 02 "served over HTTPS"; g 03 "served over HTTPS"; g 03 "exit=0"
g 04 "served over HTTPS"; g 05 "exit=5"; g 06 "expired"; g 06 "exit=5"; g 07 "exit="; g 08 "served over HTTPS"; g 09 "served over HTTPS"
g 10 "served over HTTPS"; g 11 "exit=5"; g 12 "exit="; g 13 "served over HTTPS"; g 14 "served over HTTPS"
echo "backend=$BACKEND"; echo "status=$status"; exit $status
