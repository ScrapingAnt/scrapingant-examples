#!/usr/bin/env bash
# Every wget command from the article, run against server.py on 127.0.0.1:8000.
set -uo pipefail
export LC_ALL=C LANG=C
cd "$(dirname "$0")"; rm -rf expected_output; mkdir -p expected_output; status=0
python3 server.py 2> server.log & SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT
for i in $(seq 1 20); do python3 -c "import socket; socket.create_connection(('127.0.0.1', 8000), 1)" 2>/dev/null && break; sleep 0.5; done
U=http://127.0.0.1:8000
# rec <name> <display command> <shell command>: records "$ display", stdout+stderr and the exit code
rec() { { echo "\$ $2"; bash -c "$3" 2>&1; echo "exit=$?"; } > "expected_output/$1.txt"; }
{ echo "wget: $(wget --version | head -1)"; echo "curl: $(curl --version | head -1)"; echo "python3: $(python3 --version 2>&1)"; } > expected_output/00_versions.txt

rec 01_post_data      "wget -qO- --post-data 'user=foo&lang=en' $U/echo"                                   "wget -qO- --post-data 'user=foo&lang=en' $U/echo"
rec 02_post_json      "wget -qO- --header='Content-Type: application/json' --post-data='{\"key\":\"value\"}' $U/echo"   "wget -qO- --header='Content-Type: application/json' --post-data='{\"key\":\"value\"}' $U/echo"
rec 03_post_file      "wget -qO- --header='Content-Type: application/json' --post-file=fixtures/data.json $U/echo"        "wget -qO- --header='Content-Type: application/json' --post-file=fixtures/data.json $U/echo"
rec 04_method_body    "wget -qO- --method=PUT --header='Content-Type: application/json' --body-file=fixtures/data.json $U/echo"  "wget -qO- --method=PUT --header='Content-Type: application/json' --body-file=fixtures/data.json $U/echo"
rec 05_method_post_body_data "wget -qO- --method=POST --body-data='a=1&b=2' $U/echo"                        "wget -qO- --method=POST --body-data='a=1&b=2' $U/echo"
rec 06_server_response "wget -S -qO /dev/null --post-data 'user=foo' $U/echo"                                 "wget -S -qO /dev/null --post-data 'user=foo' $U/echo"
rec 07_error_no_body  "wget -nv -O- --post-data 'x=1' $U/error400"                                          "wget -nv -O- --post-data 'x=1' $U/error400"
rec 07b_error_empty_file "wget -nv -O response.json --post-data 'x=1' $U/error400; echo \"wget exit=\$?\"; wc -c < response.json"   "cd /tmp && rm -f response.json; wget -nv -O response.json --post-data 'x=1' $U/error400; echo \"wget exit=\$?\"; wc -c < response.json | tr -d ' '"
rec 08_content_on_error "wget -nv -O- --content-on-error --post-data 'x=1' $U/error400"                       "wget -nv -O- --content-on-error --post-data 'x=1' $U/error400"
for c in 301 302 303 307 308; do
rec 09_redirect_$c    "wget -qO- --post-data 'user=foo' $U/redirect$c"                                       "wget -qO- --post-data 'user=foo' $U/redirect$c | grep -E '\"(method|content_type|body)\"'"
done
rec 10_post_file_stdin "echo 'user=foo' | wget -nv -O- --post-file=/dev/stdin $U/echo; echo 'user=foo' | wget -nv -O- --post-file=- $U/echo"   "echo 'user=foo' | wget -nv -O- --post-file=/dev/stdin $U/echo; echo 'user=foo' | wget -nv -O- --post-file=- $U/echo"
rec 11_no_encoding    "wget -qO- --post-data 'q=hello world&note=a&b=c' $U/echo"                            "wget -qO- --post-data 'q=hello world&note=a&b=c' $U/echo"
rec 12_urlencode      "wget -qO- --post-data \"\$(python3 -c 'import urllib.parse; print(urllib.parse.urlencode({\"q\": \"hello world\", \"note\": \"a&b=c\"}))')\" $U/echo"   "wget -qO- --post-data \"\$(python3 -c 'import urllib.parse; print(urllib.parse.urlencode({\"q\": \"hello world\", \"note\": \"a&b=c\"}))')\" $U/echo"
rec 13_login_cookies  "wget -qO- --save-cookies cookies.txt --keep-session-cookies --post-data 'user=foo&password=bar' $U/login && wget -qO- --load-cookies cookies.txt $U/me && grep session cookies.txt"   "cd /tmp && rm -f cookies.txt && wget -qO- --save-cookies cookies.txt --keep-session-cookies --post-data 'user=foo&password=bar' $U/login && wget -qO- --load-cookies cookies.txt $U/me && grep session cookies.txt"
rec 13b_no_cookies    "wget -nv -O- $U/me"                                                                    "wget -nv -O- $U/me"
rec 13c_save_without_keep "wget -qO- --save-cookies cookies.txt --post-data 'user=foo&password=bar' $U/login; grep -c session cookies.txt"   "cd /tmp && rm -f cookies.txt && wget -qO- --save-cookies cookies.txt --post-data 'user=foo&password=bar' $U/login; grep -c session cookies.txt; true"
rec 14_basic_auth     "wget -S -qO- --http-user=user --http-password=pass --post-data 'x=1' $U/auth"          "wget -S -qO- --http-user=user --http-password=pass --post-data 'x=1' $U/auth 2>&1 | grep -E '^  HTTP/|WWW-Authenticate|\"(method|authorization|body)\"'"
rec 15_auth_no_challenge "wget -S -qO- --auth-no-challenge --http-user=user --http-password=pass --post-data 'x=1' $U/auth"   "wget -S -qO- --auth-no-challenge --http-user=user --http-password=pass --post-data 'x=1' $U/auth 2>&1 | grep -E '^  HTTP/|WWW-Authenticate|\"(method|authorization|body)\"'"
rec 16_retry_default  "wget -nv -O- --tries=3 --post-data 'x=1' '$U/flaky?case=16'"                          "wget -nv -O- --tries=3 --post-data 'x=1' '$U/flaky?case=16'"
rec 17_retry_on_503   "wget -nv -O- --tries=3 --retry-on-http-error=503 --waitretry=1 --post-data 'x=1' '$U/flaky?case=17'"   "wget -nv -O- --tries=3 --retry-on-http-error=503 --waitretry=1 --post-data 'x=1' '$U/flaky?case=17'"
rec 18_read_timeout   "wget -nv -O- --read-timeout=1 --tries=1 --post-data 'x=1' $U/slow"                    "wget -nv -O- --read-timeout=1 --tries=1 --post-data 'x=1' $U/slow"
rec 19_curl_multipart "curl -s -F file=@fixtures/data.json -F note=hello $U/echo"                            "curl -s -F file=@fixtures/data.json -F note=hello $U/echo"
rec 20_post_data_and_file "wget -qO- --post-data 'a=1' --post-file=fixtures/form.txt $U/echo"                "wget -qO- --post-data 'a=1' --post-file=fixtures/form.txt $U/echo"
kill $SRV 2>/dev/null; sleep 0.3
# mask the wget/curl user-agent version so CI on another wget does not drift the output
sed -i.bak -E 's/"user_agent": "(Wget|curl)\/[^"]*"/"user_agent": "\1\/<version>"/; s/^  Server: .*/  Server: <server>/; s/^  Date: .*/  Date: <date>/; s/^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} /<time> /; s/boundary=-+[A-Za-z0-9]+/boundary=<boundary>/; s/"body": "-+[A-Za-z0-9]+\\r/"body": "--<boundary>\\r/; s/\\r\\n-+[A-Za-z0-9]+/\\r\\n--<boundary>/g' expected_output/*.txt; rm -f expected_output/*.bak
echo "== server log"; grep -E "^(GET|POST|PUT) " server.log | uniq -c | head -40
for f in expected_output/*.txt; do echo "=== $f"; cat "$f"; done
g() { grep -q -- "$2" "expected_output/$1"*.txt || { echo "FAILED: $1 missing '$2'"; status=1; }; }
g 01 '"method": "POST"'; g 01 'application/x-www-form-urlencoded'; g 02 '"content_type": "application/json"'; g 03 '"content_length": "36"'
g 04 '"method": "PUT"'; g 05 '"method": "POST"'; g 06 "HTTP/1.1 200"; g 07_ "ERROR 400"; g 07_ "exit=8"; g 07b "wget exit=8"; g 07b "^0$"; g 08 "field user is required"
g 09_redirect_303 '"method": "GET"'; g 09_redirect_307 '"method": "POST"'; g 09_redirect_308 '"method": "POST"'; g 10 "exit="; g 12 "q=hello+world"
g 13_ "hello foo"; g 13b "Authentication Failed"; g 13c "^0$"; g 14 '"authorization": "Basic'; g 15 '"authorization": "Basic'; g 17 '"method": "POST"'; g 17 "\[3\]"; g 18 "exit=4"; g 19 "multipart/form-data"; g 19 '"body": "--<boundary>'
grep -q '"body": "-' expected_output/19_*.txt && grep -q -- '"body": "-------' expected_output/19_*.txt && { echo "FAILED: 19 boundary not masked"; status=1; }
echo "status=$status"; exit $status
