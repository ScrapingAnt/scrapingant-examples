# A local Python forward proxy with proxy.py

Evidence for https://scrapingant.com/blog/python-proxy-server-proxy-py. This lab proves HTTP forwarding, HTTPS CONNECT with certificate verification, Basic proxy authentication, a plain-HTTP marker plugin, and upstream routing. All targets and upstreams are local, self-authored fixtures. No API key or external proxy account is needed.

## Run

Prerequisites: Python 3.12, cURL, OpenSSL, Bash, and free loopback ports 8000, 8443 and 8899–8905. The captured run used macOS; CI runs on Linux. Installation needs PyPI access; the tests need only loopback networking.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./run.sh
```

The runner creates a two-day test CA and server certificate in ignored `generated/`. Only clients given `generated/ca.pem` trust it. It never installs a CA or disables certificate verification. `set -euo pipefail` preserves failures through `tee`. Failed assertions exit nonzero, including unexpected success in negative cases.

For manual exploration, after installing:

```bash
python lab.py serve
```

Wait for `READY`. Keep that terminal running and use another terminal with the same virtualenv and working directory. Ctrl-C stops all processes owned by the lab. Do not start a second copy on the same ports. `serve` rewrites local origin/proxy logs; `run.sh` recaptures the full output set.

```bash
curl --noproxy '' --silent --show-error --fail --verbose --max-time 5 --proxy http://127.0.0.1:8899 http://localhost:8000/curl-False
curl --noproxy '' --silent --show-error --fail --verbose --max-time 5 --proxy http://127.0.0.1:8899 --cacert generated/ca.pem https://localhost:8443/curl-True
python client.py http
python client.py https
```

The generated CA is necessary only for this lab's locally signed HTTPS origin. The HTTPS client still connects to an `http://` proxy address; CONNECT carries the TLS connection to the HTTPS origin.

## Listeners and exact startup configuration

`lab.py` launches each command with the current interpreter, one worker and one acceptor, explicit loopback binding and INFO logs. The `run.txt` transcript records the expanded executable path. `PYTHONPATH` includes this packet directory for plugin imports.

| Port | Role | Extra flags |
|---|---|---|
| 8000 | JSON HTTP origin | Python stdlib fixture |
| 8443 | JSON HTTPS origin | Generated certificate |
| 8899 | Plain proxy | none |
| 8900 | Authenticated proxy | `--basic-auth lab:secret` (fake credentials) |
| 8901 | First upstream | `--plugins lab_plugins.UpstreamA` |
| 8902 | Second upstream | `--plugins lab_plugins.UpstreamB` |
| 8903 | Pool | `--plugins proxy.plugin.ProxyPoolPlugin --proxy-pool 127.0.0.1:8901 --proxy-pool 127.0.0.1:8902` |
| 8904 | Header plugin | `--plugins lab_plugins.MarkerPlugin` |
| 8905 | Broken legacy recipe | `--plugins lab_plugins.LegacyRotatingProxyPlugin` |

## Evidence files

- `lab.py`: startup polling, fixture server, client cases, assertions and bounded teardown. Clears environment proxy variables for child commands; Requests uses `trust_env=False` and explicit proxies.
- `client.py`: the small standalone Requests reader example, tested for both schemes.
- `lab_plugins.py`: working marker plugins and the old recipe, isolated for failure reproduction. Legacy endpoint ports are changed to the two fixture upstreams; the original host/port-rewriting algorithm is retained.
- `fixtures/server.cnf`: localhost certificate extensions.
- `expected_output/run.txt`: raw commands, client stdout/stderr and exit codes from the recorded run. Negative cases intentionally contain HTTP errors and a bind-error traceback.
- `expected_output/*.log`: raw proxy access logs. Correlate paths with `origin.jsonl`; pool markers are also asserted against the selected upstream's log.
- `expected_output/summary.json`: denominators and measured counts. Includes two additional reader-client requests beyond the four forwarding matrix cases.
- `expected_output/proxy-help.txt`, `release.json`, `proxy_pool.source.txt`: package help, release metadata and exact installed pool source, verified byte-for-byte against upstream release commit `3b9964b683dccf4507380fd17d3403ac0cf64342`.
- `evidence.yaml`: claims, sources, dependencies and scope.

## Limitations

Pool selection is random per client connection, not guaranteed round-robin. Each of the 20 pool requests uses a fresh Requests session. Counts will vary. The two upstreams share one machine; this is not a public-IP rotation, throughput or reliability benchmark. Literal private IP destinations bypass this release's pool; the routing test intentionally uses `localhost` as a hostname. No retry/failover claim is made.

The old recipe produces HTTP 400 in this fixture, with no origin hit. That result is not a universal outcome for every target or upstream. Missing/wrong credentials produce HTTP 407 here; the captured cURL build exits 22 for both plain HTTP and failed CONNECT (the runner also accepts exit 56 for CONNECT on other builds). Requests exposes an HTTP 407 response for HTTP and raises ProxyError for HTTPS. Messages and OS error numbers may differ elsewhere.

The refused-connection test releases an allocated local port immediately before probing it. Unexpected port reuse makes the assertion fail rather than reporting a false success. No system-wide process killing or trust-store changes occur. Local keys and certificates are generated anew and excluded from version control.
