#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
dotnet restore --locked-mode
dotnet build --no-restore --configuration Release
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
dotnet run --no-build --configuration Release -- --test | tee "$scratch/tests.txt"
dotnet run --no-build --configuration Release > "$scratch/css.json"
dotnet run --no-build --configuration Release -- --hap > "$scratch/xpath.json"
diff "$scratch/css.json" "$scratch/xpath.json"
if [[ "${1:-}" == "--capture" ]]; then
  mkdir -p expected_output
  cp "$scratch/"* expected_output/
else
  diff expected_output/css.json "$scratch/css.json"
  diff expected_output/xpath.json "$scratch/xpath.json"
fi
cat "$scratch/css.json"
