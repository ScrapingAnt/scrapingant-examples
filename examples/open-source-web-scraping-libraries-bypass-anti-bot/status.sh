#!/usr/bin/env bash
# Records the public status of each library in the article: GitHub repo (stars, last push, archived)
# and the latest package release on PyPI or npm. Needs gh (authenticated) and curl.
set -euo pipefail
repo() { gh api "repos/$1" --jq '"\(.full_name) | stars \(.stargazers_count) | last push \(.pushed_at[:10]) | archived \(.archived) | \(.license.spdx_id // "-")"'; }
pypi() { curl -s "https://pypi.org/pypi/$1/json" | python3 -c "import sys,json;d=json.load(sys.stdin);v=d['info']['version'];print('  pypi $1', v, d['releases'][v][0]['upload_time'][:10])"; }
npmv() { echo "  npm $1 $(npm view "$1" version) $(npm view "$1" time --json | python3 -c "import sys,json;d=json.load(sys.stdin);print(max((t for k,t in d.items() if k not in ('created','modified')))[:10])")"; }
echo "checked $(date -u +%Y-%m-%d)"
repo omkarcloud/botasaurus; pypi botasaurus
repo Vinyzu/Botright; pypi botright
repo ultrafunkamsterdam/nodriver; pypi nodriver
repo kaliiiiiiiiii/undetected-playwright-python; pypi undetected-playwright
repo Kaliiiiiiiiii-Vinyzu/patchright; pypi patchright
repo daijro/camoufox; pypi camoufox
repo berstend/puppeteer-extra; npmv puppeteer-extra-plugin-stealth
repo lexiforest/curl_cffi; pypi curl-cffi
repo ScrapeGraphAI/Scrapegraph-ai; pypi scrapegraphai
