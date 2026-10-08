#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
dotnet restore --locked-mode
dotnet build --no-restore --configuration Release
scratch=$(mktemp)
trap 'rm -f "$scratch"' EXIT
python3 test_download.py > "$scratch"
if [[ "${1:-}" == "--capture" ]]; then
  mkdir -p expected_output
  cp "$scratch" expected_output/cases.json
else
  python3 verify_capture.py expected_output/cases.json "$scratch"
fi
cat "$scratch"
