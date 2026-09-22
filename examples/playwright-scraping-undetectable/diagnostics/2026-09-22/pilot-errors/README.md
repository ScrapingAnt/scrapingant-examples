# Excluded harness pilots

Two first-pass Node runs captured screenshots but did not serialize their DOM snapshots: the adapter passed a JavaScript function expression as a string rather than a callable. Node returned undefined and the verdict/row assertions failed. These are harness errors, not evidence of detector outcomes.

After fixing the shared extractor invocation in node/probe.cjs, these two configurations were run again after the original matrix completed. Their replacement observations are in results/ and screenshots/. The original JSON/screenshots remain here and are excluded by the summarizer. Thus the repaired repetition1 observations occurred after repetition2; run timestamps are authoritative.
