import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
def manifest():
    paths = [p for p in ROOT.iterdir() if p.is_file() and p.name != 'verification.json']
    paths += list((ROOT / 'fixtures').rglob('*')) + list((ROOT / 'expected_output').rglob('*'))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths) if p.is_file()}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--write', action='store_true'); args = parser.parse_args()
    document = {'algorithm': 'sha256', 'files': manifest()}
    path = ROOT / 'verification.json'
    if args.write: path.write_text(json.dumps(document, indent=2) + '\n')
    elif json.loads(path.read_text()) != document: raise SystemExit('Manifest mismatch')
    print(json.dumps({'verified_files': len(document['files'])}))
