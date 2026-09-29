#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1
mkdir -p expected_output
python3 verify.py | tee expected_output/verification.txt
python3 check_declarations.py --format json | tee expected_output/report.json
python3 check_declarations.py --format text | tee expected_output/report.txt
python3 - <<'PY' | tee expected_output/run-meta.json
from datetime import datetime, timezone
import hashlib, json, platform
from pathlib import Path
print(json.dumps({
    'recorded_at': datetime.now(timezone.utc).isoformat(),
    'python': platform.python_version(), 'os': platform.system(), 'machine': platform.machine(),
    'command': './run.sh', 'completed_steps_exit_status': 0,
    'network_requests_during_run': 0, 'api_calls': 0, 'api_credits': 0,
    'sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(Path('fixtures').glob('*'))}
}, indent=2))
PY
