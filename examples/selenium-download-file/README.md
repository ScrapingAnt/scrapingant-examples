# Selenium downloads: Chrome and Firefox

Evidence for https://scrapingant.com/blog/selenium-download-file.

## Prerequisites and reproduction

Use Python 3.12 and install Chrome. Firefox's `browser_version = "stable"` lets
Selenium Manager provision a stable Firefox in its browser cache instead of
using an old system install. Network access is required for Python packages
and the initial browser/driver downloads. A graphical desktop is needed for
headed runs. Once provisioned, payload downloads use only a loopback HTTP server.

From a checkout of tag `selenium-download-file/2026-09-21`:

```bash
cd examples/selenium-download-file
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./run.sh
```

`run.sh` captures commands and real output in `expected_output/`. `set -euo
pipefail` propagates a failing script even when stdout is piped through `tee`.
The default matrix includes headed and headless sessions for both browsers.
For a machine without a graphical desktop, `HEADLESS_ONLY=1 ./run.sh` explicitly
excludes headed sessions; that is a smaller matrix, not the recorded full run.

```bash
python chrome_download.py
python firefox_download.py
python chrome_download.py --headed
python firefox_download.py --headed
python chrome_download.py --output generated/chrome
python -m unittest -v test_wait
```

The first four commands verify three files per browser/mode and remove their
temporary download folders on exit. `--output` retains files for inspection;
it must name an empty or nonexistent directory. Choose a new folder for a
second retained run instead of deleting existing downloads automatically.

## What is tested

- Fresh Chrome/Firefox profiles, absolute download directories and headless flags.
- A 14-byte CSV attachment, a 65,536-byte delayed binary attachment and a PDF attachment.
- `Content-Type`, `Content-Disposition: attachment` and `Content-Length` set by
  `fixture_server.py`; PDF viewer preferences applied explicitly.
- Element clickability separately from file verification; a known length and
  SHA-256 digest are required for the latter.
- Empty-directory preflight rejects stale output. The helper rejects partial
  suffixes, a truncated payload and a wrong checksum, and times out on a missing file.
- Real interrupted HTTP transfers in headless Chrome and Firefox must time out.
- Direct HTTP retrieval and HTTP 404 handling, plus errors from the old article's APIs.

`test_wait.py` was first run against the article's existence-only approach:
five assertions failed (two temporary suffixes, stale directory, truncated
payload, wrong checksum). The revised helper passes all seven tests.

## Fixture ownership and scope

All fixture content is self-authored and public under this repository's license.
Static files live in `../../fixtures/selenium-download-file/`. The HTML page's
`/download/*` routes require the packet's loopback server, not a generic static
server or GitHub Pages. GitHub Pages can expose the static payloads but does not
reproduce the response headers, delays or interrupted-transfer behavior.

The PDF has a single text page; its object offsets and stream length are checked
when preparing the fixture. Payloads are small; the helper reads the entire file
for verification. It is intentionally not a large-file streaming verifier.

Results describe the recorded macOS/browser versions. Windows, Linux, Grid,
containers, remote filesystem transfer, concurrent downloads, authentication,
blob URLs and arbitrary production file formats were not tested. Known length
and checksum are an application-level oracle: a stable size alone is not proof
that an arbitrary download succeeded. Temporary suffixes are not a browser-neutral
completion API. Selenium's file-download guidance recommends an HTTP library
when the task only needs the file's contents.

## Maintenance

Re-run on Selenium or browser updates, or when the article's examples fail. Do
not replace committed observations with guessed output. `evidence.yaml` identifies
the tested source commit; the dated Git tag identifies the complete packet.
The browser-dependent full matrix is not in the generic CI allow-list: that
workflow does not provision a headed display/browser matrix. Record any future
CI run as a separate environment, not as the local macOS result.
