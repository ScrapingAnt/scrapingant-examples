# Preserved exploratory results

These files are historical failures, excluded from the final 72 extraction-case and 24 diagnostic denominators.

1. `test-first-red.json`: 16 test methods, 19 failures including subtest failures, zero errors, against deliberately permissive validator/summary stubs. The independently written oracle preceded browser capture.
2. `test-first-green.json`: the same initial 16 tests passed after validation was implemented.
3. `environment-failure.json`: the first quickstart could not bind its loopback server inside the restricted process sandbox. It failed before browser startup. The unchanged command was subsequently run with permission for local browser processes and a loopback listener; Chromium's browser sandbox remained enabled.
4. `initial-chromium.json` and `initial-firefox.json`: complete initial three-round captures. `text_exact` returned an empty `records` list in every round, instead of the literal Café Mug record. The strict summary rejected the matrix.
5. `integrity-red.json`: after adding stronger summary/integrity regressions, 25 tests ran with eight failures and zero errors before those checks were implemented.
6. `schema-red.json`: two failing subtests exposed Python equality accepting boolean true and float 1.0 as schema version 1. Requiring an integer schema type fixed both without changing the captured browser data.

The text-filter bug came from an inner `has=` locator prefixed with `#catalog`. Playwright evaluates that locator relative to each candidate row, which has no descendant `#catalog`. The fixed extraction uses `page.get_by_text('Café Mug', exact=True)` as the relative inner query. The final `text_exact` case retains the ancestor-prefixed query as an explicit wrong control and records its empty SKU list beside the correct full record. No expected record was weakened to accept the failing output.

The historical test counts are not the final test-suite count. Raw JSON here records what ran at each stage. Host filesystem paths were omitted from the environment-failure record; browser captures contain no host paths.
