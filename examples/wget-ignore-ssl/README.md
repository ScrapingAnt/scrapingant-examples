# How to Ignore SSL Certificate Errors With Wget

Evidence packet for https://scrapingant.com/blog/wget-ignore-ssl

## What this demonstrates
Every wget TLS command in the article, run against two local HTTPS servers started by `run.sh`: `https://localhost:8443` with a self-signed certificate (SAN `localhost`) and `https://localhost:8444` with a certificate that expired in February 2024. Cases: the default failure and exit code, `--no-check-certificate`, `--ca-certificate`, `--ca-directory` after `openssl rehash`, hostname mismatch by IP, expired certificate, `SSL_CERT_FILE`, `.wgetrc` and `-e`, `--pinnedpubkey` (right hash, wrong hash, without `--no-check-certificate`), `--secure-protocol`, and the curl equivalents.

## Run
```bash
pip install -r requirements.txt   # cryptography, to generate the two certificates
./run.sh
```
Needs `wget`, `curl`, `openssl` and Python 3. `run.sh` sets `LC_ALL=C` so messages are in English and masks wget's timestamps.

## The build matters
`expected_output/00_versions.txt` records `wget --version`'s `+ssl/openssl` or `+ssl/gnutls` flag. Case 07 (`SSL_CERT_FILE`) is expected to succeed on an OpenSSL build and to fail on a GnuTLS build (Debian/Ubuntu packages); its check accepts either outcome. The recorded run here is the OpenSSL build; the monthly CI run on Ubuntu shows the GnuTLS result in its log.

## Files
- `run.sh` — generates certificates, starts the servers, records one file per case (command, output, exit code), checks key strings
- `gen_certs.py`, `server.py` — certificate generation and the two servers (IPv4 and IPv6 loopback)
- `fixtures/index.html` — the page served
- `expected_output/` — captured output from the last recorded run (`evidence.yaml: tested_at`)

## Limitations
- One wget build per run; the `SSL_CERT_FILE` result depends on the TLS backend.
- Client certificates and CRLs are not exercised; system-store update commands are documented in the article, not run.
