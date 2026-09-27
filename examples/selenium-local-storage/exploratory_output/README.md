# Excluded exploratory captures

`chrome-smoke.json` and `chrome-smoke.log` are the first one-round Chrome smoke test before the URL-selected page and full snapshot diagnostic were added. It passed 19 scenario assertions.

`pre-hardening/` preserves the first complete three-round Chrome/Firefox captures. They preceded explicit proxy isolation and restoring Chrome's default sandbox. They passed their 120 scenario assertions but are superseded by the final `expected_output/` run.

No browser failure occurred in these exploratory runs. These files are retained as development history, not included in the final measurement denominators. The summary reads only explicitly supplied files and rejects one-round, obsolete-schema, or failed captures.

`pre-document-origin-guard/` preserves the sandbox/proxy-hardened run before the guard was tightened to query `location.origin` in the currently selected script document instead of relying on the top-level driver URL. Its 120 passed assertions are excluded from final counts.
