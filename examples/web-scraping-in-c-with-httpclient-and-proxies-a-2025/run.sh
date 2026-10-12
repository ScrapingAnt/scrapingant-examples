#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export DOTNET_CLI_TELEMETRY_OPTOUT=1
export DOTNET_GENERATE_ASPNET_CERTIFICATE=false
export DOTNET_NOLOGO=1
export DOTNET_CLI_HOME="${DOTNET_CLI_HOME:-$PWD/.dotnet-home}"
export NUGET_PACKAGES="${NUGET_PACKAGES:-$PWD/.nuget}"
dotnet_cmd="${DOTNET:-dotnet}"
if [[ "$("$dotnet_cmd" --version)" != "10.0.401" ]]; then
  echo 'Install the pinned .NET SDK 10.0.401 first' >&2
  exit 1
fi
if [[ $# -gt 1 || ($# -eq 1 && "$1" != '--capture') ]]; then
  echo 'Usage: ./run.sh [--capture]' >&2
  exit 2
fi
mkdir -p actual_output
# Dependency setup may download the locked NuGet package; executable checks use only fake handlers.
"$dotnet_cmd" restore --locked-mode --configfile NuGet.Config -p:NuGetAudit=false --nologo > actual_output/build.txt
"$dotnet_cmd" build --no-restore --configuration Release --nologo >> actual_output/build.txt
"$dotnet_cmd" run --no-restore --no-build --configuration Release -- --offline | tee actual_output/offline.txt
python3 verify_output.py | tee actual_output/oracle.txt
python3 verify_output.py --controls | tail -n 1 | tee actual_output/oracle-controls.txt
"$dotnet_cmd" run --no-restore --no-build --configuration Release -- --offline-jsonld | tee actual_output/jsonld.txt
python3 verify_jsonld.py | tee actual_output/jsonld-oracle.txt
python3 verify_jsonld.py --controls | tail -n 1 | tee actual_output/jsonld-oracle-controls.txt
python3 live-captures/verify_captures.py | tee actual_output/marker-captures.txt
python3 live-captures/product-jsonld/verify_capture.py | tee actual_output/native-capture.txt
python3 live-captures/product-jsonld/verify_capture.py --controls | tail -n 1 | tee actual_output/native-capture-controls.txt
if [[ "${1:-}" == '--capture' ]]; then
  mkdir -p expected_output
  cp actual_output/offline.txt actual_output/results.json actual_output/oracle.txt actual_output/oracle-controls.txt expected_output/
  cp actual_output/jsonld.txt actual_output/jsonld-results.json actual_output/jsonld-oracle.txt actual_output/jsonld-oracle-controls.txt expected_output/
  cp actual_output/marker-captures.txt actual_output/native-capture.txt actual_output/native-capture-controls.txt expected_output/
  echo 'Captured offline outputs; live API calls=0'
else
  diff -u expected_output/offline.txt actual_output/offline.txt
  diff -u expected_output/results.json actual_output/results.json
  diff -u expected_output/oracle.txt actual_output/oracle.txt
  diff -u expected_output/oracle-controls.txt actual_output/oracle-controls.txt
  diff -u expected_output/jsonld.txt actual_output/jsonld.txt
  diff -u expected_output/jsonld-results.json actual_output/jsonld-results.json
  diff -u expected_output/jsonld-oracle.txt actual_output/jsonld-oracle.txt
  diff -u expected_output/jsonld-oracle-controls.txt actual_output/jsonld-oracle-controls.txt
  diff -u expected_output/marker-captures.txt actual_output/marker-captures.txt
  diff -u expected_output/native-capture.txt actual_output/native-capture.txt
  diff -u expected_output/native-capture-controls.txt actual_output/native-capture-controls.txt
  echo 'Recorded offline outputs match'
fi
