"""Validate the committed manifest; never regenerate it as part of verification."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
manifest = json.loads((root/'verification.json').read_text())
for name, expected in manifest['sha256'].items():
    path = root/name
    if path.resolve().parent != root and root not in path.resolve().parents:
        raise ValueError('manifest path escapes the packet')
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError('hash mismatch: '+name)
print(json.dumps({'verified_files': len(manifest['sha256']), 'algorithm': 'SHA-256', 'passed': True}))
