"""Deliberately wrong completeness-blind absence diagnostic, for comparison."""
import json
from pathlib import Path
from snapshot import parse_snapshot

ROOT = Path(__file__).resolve().parent
baseline = parse_snapshot((ROOT / "fixtures/baseline.html").read_text())
truncated = parse_snapshot((ROOT / "fixtures/truncated.html").read_text())
missing = sorted({r["asin"] for r in baseline["records"]} - {r["asin"] for r in truncated["records"]})
print(json.dumps({"demonstration": "Wrong: ignores snapshot completeness", "missing_asins": missing,
                  "missing_count": len(missing), "current_complete": truncated["complete"]}, indent=2, sort_keys=True))
