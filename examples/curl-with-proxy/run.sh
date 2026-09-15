#!/usr/bin/env bash
# Every command from the article, run against proxies started here:
#   127.0.0.1:8080  HTTP proxy WITH Basic auth (proxy.py)  -> answers a real 407
#   127.0.0.1:8081  HTTP proxy without auth (pproxy)
#   127.0.0.1:1080  SOCKS5 proxy with auth (pproxy)
#   127.0.0.1:8000  local HTTP target (python http.server serving fixtures/)
# Public HTTPS target: the scrapingant-examples fixture on GitHub Pages.
set -uo pipefail
cd "$(dirname "$0")"; rm -rf expected_output; mkdir -p expected_output; status=0
T="https://scrapingant.github.io/scrapingant-examples/fixtures/dynamic-delayed.html"
H="http://127.0.0.1:8000/index.html"

proxy --hostname 127.0.0.1 --port 8080 --basic-auth user:pass --log-level WARNING > proxy-http.log 2>&1 & P1=$!
pproxy -l "socks5://127.0.0.1:1080#user:pass" > proxy-socks.log 2>&1 & P2=$!
pproxy -l "http://127.0.0.1:8081" > proxy-open.log 2>&1 & P3=$!
python -m http.server 8000 --bind 127.0.0.1 --directory fixtures > target.log 2>&1 & P4=$!
trap 'kill $P1 $P2 $P3 $P4 2>/dev/null' EXIT
sleep 2

# rec <name> <display command> <shell command>: records "$ display", the output and the exit code
rec() { { echo "\$ $2"; bash -c "$3" 2>&1; echo "exit=$?"; } > "expected_output/$1.txt"; }
# vrec: same, but for -v transcripts: keep the protocol lines only and no exit code (the pipe hides it)
vrec() { { echo "\$ $2"; bash -c "$3" 2>&1 | tr -d '\r' | perl -pe 's/(?<![\d.])(?!127\.)(\d{1,3}\.){3}\d{1,3}(?![\d.])/<ip>/g' | grep -E '^(> (CONNECT|GET|Host|Proxy-Authorization)|< HTTP|< Proxy-Authenticate|\* (Uses proxy|CONNECT tunnel|Connected to|SOCKS5|Host .* was resolved))'; } > "expected_output/$1.txt"; }

{ echo "curl: $(curl --version | head -1)"; echo "proxy.py: $(pip show proxy.py | awk '/^Version/{print $2}')  pproxy: $(pip show pproxy | awk '/^Version/{print $2}')"; } > expected_output/00_versions.txt

rec  01_basic_x            "curl -x http://127.0.0.1:8081 -o /dev/null -w '%{http_code}\n' $T"                                  "curl -s -x http://127.0.0.1:8081 -o /dev/null -w '%{http_code}\n' $T"
rec  02_proxy_user         "curl -x http://127.0.0.1:8080 --proxy-user user:pass -o /dev/null -w '%{http_code}\n' $T"           "curl -s -x http://127.0.0.1:8080 --proxy-user user:pass -o /dev/null -w '%{http_code}\n' $T"
rec  03_creds_in_url       "curl -x http://user:pass@127.0.0.1:8080 -o /dev/null -w '%{http_code}\n' $T"                         "curl -s -x http://user:pass@127.0.0.1:8080 -o /dev/null -w '%{http_code}\n' $T"
rec  04_no_creds_https     "curl -x http://127.0.0.1:8080 -o /dev/null -w '%{http_code}\n' $T"                                  "curl -s -x http://127.0.0.1:8080 -o /dev/null -w '%{http_code}\n' $T"
rec  05_no_creds_http      "curl -x http://127.0.0.1:8080 -o /dev/null -w '%{http_code}\n' $H"                                  "curl -s -x http://127.0.0.1:8080 -o /dev/null -w '%{http_code}\n' $H"
vrec 06_wrong_creds        "curl -v -x http://127.0.0.1:8080 --proxy-user user:wrong -o /dev/null $T"                            "curl -sv -x http://127.0.0.1:8080 --proxy-user user:wrong -o /dev/null $T"
vrec 07_https_connect      "curl -v -x http://127.0.0.1:8080 --proxy-user user:pass -o /dev/null $T"                             "curl -sv -x http://127.0.0.1:8080 --proxy-user user:pass -o /dev/null $T"
vrec 08_http_plain         "curl -v -x http://127.0.0.1:8080 --proxy-user user:pass -o /dev/null $H"                             "curl -sv -x http://127.0.0.1:8080 --proxy-user user:pass -o /dev/null $H"
vrec 09_socks5             "curl -v -x socks5://user:pass@127.0.0.1:1080 -o /dev/null $T"                                        "curl -sv -x socks5://user:pass@127.0.0.1:1080 -o /dev/null $T"
vrec 10_socks5h            "curl -v -x socks5h://user:pass@127.0.0.1:1080 -o /dev/null $T"                                       "curl -sv -x socks5h://user:pass@127.0.0.1:1080 -o /dev/null $T"
vrec 11_env_https_proxy    "https_proxy=http://127.0.0.1:8081 curl -v -o /dev/null $T"                                           "https_proxy=http://127.0.0.1:8081 curl -sv -o /dev/null $T"
vrec 12_env_http_proxy     "http_proxy=http://127.0.0.1:8081 curl -v -o /dev/null $H"                                            "http_proxy=http://127.0.0.1:8081 curl -sv -o /dev/null $H"
vrec 13_env_HTTP_PROXY     "HTTP_PROXY=http://127.0.0.1:8081 curl -v -o /dev/null $H"                                            "HTTP_PROXY=http://127.0.0.1:8081 curl -sv -o /dev/null $H"
vrec 14_env_ALL_PROXY      "ALL_PROXY=http://127.0.0.1:8081 curl -v -o /dev/null $T"                                             "ALL_PROXY=http://127.0.0.1:8081 curl -sv -o /dev/null $T"
vrec 15_no_proxy_env       "https_proxy=http://127.0.0.1:8081 no_proxy=scrapingant.github.io curl -v -o /dev/null $T"           "https_proxy=http://127.0.0.1:8081 no_proxy=scrapingant.github.io curl -sv -o /dev/null $T"
vrec 16_noproxy_flag       "https_proxy=http://127.0.0.1:8081 curl -v --noproxy '*' -o /dev/null $T"                             "https_proxy=http://127.0.0.1:8081 curl -sv --noproxy '*' -o /dev/null $T"
vrec 17_x_empty            "https_proxy=http://127.0.0.1:8081 curl -v -x '' -o /dev/null $T"                                     "https_proxy=http://127.0.0.1:8081 curl -sv -x '' -o /dev/null $T"
vrec 18_x_overrides_env    "https_proxy=http://127.0.0.1:9999 curl -v -x http://127.0.0.1:8081 -o /dev/null $T"                  "https_proxy=http://127.0.0.1:9999 curl -sv -x http://127.0.0.1:8081 -o /dev/null $T"
mkdir -p curlhome && printf 'proxy = "http://127.0.0.1:8080"\nproxy-user = "user:pass"\n' > curlhome/.curlrc
vrec 19_curlrc             "CURL_HOME=./curlhome curl -v -o /dev/null $T"                                                       "CURL_HOME=./curlhome curl -sv -o /dev/null $T"
vrec 24_curlrc_vs_x        "CURL_HOME=./curlhome curl -v -x http://127.0.0.1:8081 -o /dev/null $T"                              "CURL_HOME=./curlhome curl -sv -x http://127.0.0.1:8081 -o /dev/null $T"
rm -rf curlhome
rec  20_connection_refused "curl -x http://127.0.0.1:9999 -o /dev/null -w '%{http_code}\n' $T"                                  "curl -s -x http://127.0.0.1:9999 -o /dev/null -w '%{http_code}\n' $T"
rec  21_unresolvable_proxy "curl -x http://proxy.invalid:8080 -o /dev/null -w '%{http_code}\n' $T"                              "curl -s -x http://proxy.invalid:8080 -o /dev/null -w '%{http_code}\n' $T"
vrec 22_no_proxy_leading_dot "https_proxy=http://127.0.0.1:8081 no_proxy=.github.io curl -v -o /dev/null $T"                    "https_proxy=http://127.0.0.1:8081 no_proxy=.github.io curl -sv -o /dev/null $T"
vrec 23_noproxy_beats_x    "curl -v -x http://127.0.0.1:8081 --noproxy '*' -o /dev/null $T"                                      "curl -sv -x http://127.0.0.1:8081 --noproxy '*' -o /dev/null $T"

for f in expected_output/*.txt; do echo "=== $f"; cat "$f"; done
for n in 01 02 03 11 12 15 16 17 18 19; do grep -q "200" expected_output/${n}_*.txt || { echo "FAILED: $n"; status=1; }; done
grep -q "exit=56" expected_output/04_*.txt || status=1; grep -q "^407" expected_output/05_*.txt || status=1
grep -q "407" expected_output/06_*.txt || status=1; grep -q "CONNECT" expected_output/07_*.txt || status=1
grep -q "locally resolved" expected_output/09_*.txt || status=1; grep -q "remotely resolved" expected_output/10_*.txt || status=1
grep -q "exit=7" expected_output/20_*.txt || status=1; grep -q "exit=5" expected_output/21_*.txt || status=1
grep -q "Connected to scrapingant.github.io" expected_output/22_*.txt || status=1; grep -q "Connected to scrapingant.github.io" expected_output/23_*.txt || status=1
grep -q "port 8081" expected_output/24_*.txt || status=1
echo "status=$status"; exit $status
