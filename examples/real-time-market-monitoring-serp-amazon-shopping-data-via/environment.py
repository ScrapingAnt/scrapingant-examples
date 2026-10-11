"""Capture runtime versions and byte hashes without hostnames or credentials."""
import hashlib
import json
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parent
files = sorted([*ROOT.glob("*.py"), ROOT / "run.sh", ROOT / "requirements.txt", *ROOT.glob("fixtures/*"),
                *[p for p in ROOT.glob("expected_output/*") if p.name != "environment.json"]])
print(json.dumps({"tested_at": "2026-10-11", "python": platform.python_version(), "implementation": platform.python_implementation(),
                  "os": platform.system(), "os_release": platform.release(), "third_party_dependencies": [],
                  "browser": "not used", "network_calls": 0, "provider_calls": 0,
                  "sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}, indent=2, sort_keys=True))
