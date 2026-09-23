# Superseded control diagnostics

These were captured before the paid pilot and are excluded from the final five passing rejection assertions.

- `initial-geetest-v4-negative-control.json`: the early whitelist discarded the schema-error details, and the early assertion treated absence of acceptance as sufficient. Its recorded `control_assertion_passed: true` is therefore not evidence of solution rejection. The harness was changed to retain typed errors, use a validly shaped generation timestamp, and require an explicit rejection. The final sibling record captures `result: fail`.
- `second-recaptcha-invisible-negative-control.json`: fixture setup failed because the page had two response fields. The harness was changed to wait for the first field and fill all fields before submitting. The final sibling record captures an explicit rejection.

No paid tasks were created by these controls. Historical outcomes are kept as recorded rather than rewritten to look successful under the final assertions.
