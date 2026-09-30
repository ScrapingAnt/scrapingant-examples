#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p expected_output
{ date -u +%Y-%m-%dT%H:%M:%SZ; uname -a; java -version; mvn -version; } > expected_output/environment.txt 2>&1
mvn -B -ntp clean test 2>&1 | tee expected_output/tests.txt
mvn -B -ntp dependency:tree 2>&1 | tee expected_output/dependencies.txt
mvn -B -ntp dependency:build-classpath -Dmdep.outputFile=target/classpath.txt -DincludeScope=runtime > expected_output/classpath-build.txt 2>&1
classpath="target/classes:$(cat target/classpath.txt)"
: > expected_output/cases.tsv
printf 'case\texpected_exit\tactual_exit\n' >> expected_output/cases.tsv
temporary_directory=""
trap 'if [ -n "$temporary_directory" ]; then rm -rf "$temporary_directory"; fi' EXIT
cases=(success empty missing-field timeout duplicate mismatch)
expected=(0 0 2 3 2 2)
for i in "${!cases[@]}"; do
  scenario="${cases[$i]}"
  # A fresh path lets us verify failures create no output; old output preservation is tested separately.
  temporary_directory="$(mktemp -d)"
  destination="$temporary_directory/catalog.json"
  status=0
  java -cp "$classpath" example.Main "$scenario" "$destination" > "expected_output/$scenario.stdout.txt" 2> "expected_output/$scenario.stderr.txt" || status=$?
  printf '%s\t%s\t%s\n' "$scenario" "${expected[$i]}" "$status" | tee -a expected_output/cases.tsv
  test "$status" -eq "${expected[$i]}"
  if [ "$status" -ne 0 ]; then test ! -e "$destination"; fi
  if [ "$scenario" = success ]; then cp "$destination" expected_output/catalog.json; fi
  rm -rf "$temporary_directory"
  temporary_directory=""
done
