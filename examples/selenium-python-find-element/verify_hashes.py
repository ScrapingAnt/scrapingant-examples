"""Freeze or verify public source/documentation and captured artifact hashes."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def hashes():
    paths = [path for path in ROOT.iterdir() if path.is_file() and path.name != 'verification.json']
    paths += list((ROOT / 'fixtures').glob('*'))
    paths += list((ROOT / 'expected_output').rglob('*'))
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths) if path.is_file()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    path = ROOT / 'verification.json'
    actual = {'algorithm': 'sha256', 'files': hashes()}
    if args.write:
        path.write_text(json.dumps(actual, indent=2) + '\n')
    elif json.loads(path.read_text()) != actual:
        raise SystemExit('Manifest mismatch: source or captured artifact changed')
    print(f"Verified {len(actual['files'])} files" if not args.write else f"Recorded {len(actual['files'])} files")


if __name__ == '__main__':
    main()
