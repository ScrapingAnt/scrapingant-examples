# How to Ignore SSL Certificate Errors With Wget

Evidence packet for https://scrapingant.com/blog/wget-ignore-ssl

## What this demonstrates
Every wget TLS command in the article, run against three local HTTPS servers started by `run.sh`: `https://localhost:8443` with a self-signed certificate (SAN `localhost`), `https://localhost:8444` with a certificate whose validity ended on 2024-02-01, and `https://localhost:8445` with a leaf certificate issued by a local "Example Internal CA". Cases: the default failure and exit code, `--no-check-certificate` (also against the expired server), `--ca-certificate` (local server, internal CA, and a public site to show it adds to the system store), `--ca-directory` after `openssl rehash`, hostname mismatch by IP, expired certificate, `SSL_CERT_FILE`, `.wgetrc` and `-e`, `--pinnedpubkey` (right hash, wrong hash, without `--no-check-certificate`), `--secure-protocol`, and the curl equivalents.

## Run
```bash
pip install -r requirements.txt   # cryptography, to generate the two certificates
./run.sh
```
Needs `wget`, `curl`, `openssl` and Python 3. `run.sh` sets `LC_ALL=C` so messages are in English and masks wget's timestamps.

## The build matters
`expected_output/00_versions.txt` records `wget --version`'s `+ssl/openssl` or `+ssl/gnutls` flag and the TLS library the binary links. The recorded `run.sh` is the OpenSSL build (Homebrew, macOS); Ubuntu's package is also an OpenSSL build, so CI records the same family. Debian's package links GnuTLS: `run-gnutls-docker.sh` runs the core cases (default, `--no-check-certificate`, `--ca-certificate` locally and against a public site, `--ca-directory` against a public site, `SSL_CERT_FILE`) inside `debian:bookworm-slim` and writes `expected_output/gnutls/`, which `run.sh` leaves in place. The container commands use `-4` (its server listens on IPv4 only) and `/tmp/certs`. Measured: `SSL_CERT_FILE` works on the OpenSSL build and is ignored on the GnuTLS build; `--ca-certificate` works on both and adds to the system store on both; `--ca-directory` is additive on the OpenSSL build only; the error messages differ between the two.

## Files
- `run.sh` — generates certificates, starts the servers, records one file per case (command, output, exit code), checks key strings
- `run-gnutls-docker.sh` — the GnuTLS counterpart in a Debian container (needs Docker; not run in CI)
- `gen_certs.py`, `server.py` — certificate generation (self-signed, expired, internal CA + leaf) and the three servers (IPv4 and IPv6 loopback)
- `fixtures/index.html` — the page served
- `expected_output/` — captured output from the last recorded run (`evidence.yaml: tested_at`)

## Limitations
- `run.sh` records one wget build; the GnuTLS run needs Docker and is refreshed by hand.
- Client certificates and CRLs are not exercised; system-store update commands are documented in the article, not run.
