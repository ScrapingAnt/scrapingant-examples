"""SHA-256 artifact inventory; source commit and independent CI remain separate gates."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

SOURCE_FILES = {
    ".gitignore", "README.md", "browser_matrix.py", "evidence.yaml", "expectations.py",
    "extract.py", "fixtures/catalog.html", "fixtures/frame.html", "integrity.py",
    "local_server.py", "offline_checks.py", "oracle.py", "quickstart.py", "report.md",
    "requirements-lock.txt", "requirements.txt", "run.sh", "summarize.py",
    "test_integrity.py", "test_oracle.py",
}
ARTIFACT_FILES = {
    "expected_output/chromium.json", "expected_output/firefox.json",
    "expected_output/offline-checks.json", "expected_output/quickstart.json",
    "expected_output/summary.json", "expected_output/dependencies.txt",
    "exploratory/environment-failure.json", "exploratory/initial-chromium.json",
    "exploratory/initial-firefox.json", "exploratory/integrity-red.json",
    "exploratory/test-first-red.json", "exploratory/test-first-green.json",
    "exploratory/schema-red.json", "exploratory/README.md",
}


def checked_path(root, name):
    relative = PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("unsafe manifest path")
    path = root / name
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("missing or unsafe artifact")
    return path


def verify_manifest(root, manifest, expected_paths):
    if set(manifest) != {"schema", "sha256"} or type(manifest["schema"]) is not int or manifest["schema"] != 1:
        raise ValueError("invalid manifest schema")
    if set(manifest["sha256"]) != expected_paths:
        raise ValueError("artifact inventory differs")
    for name, digest in manifest["sha256"].items():
        actual = hashlib.sha256(checked_path(root, name).read_bytes()).hexdigest()
        if actual != digest:
            raise ValueError("artifact digest differs: " + name)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true", help="Explicitly replace manifest after evidence review")
    args = parser.parse_args()
    root = Path(__file__).parent
    paths = SOURCE_FILES | ARTIFACT_FILES
    target = root / "manifest.json"
    if args.freeze:
        document = {"schema": 1, "sha256": {name: hashlib.sha256(checked_path(root, name).read_bytes()).hexdigest() for name in sorted(paths)}}
        target.write_text(json.dumps(document, indent=2) + "\n")
    document = json.loads(target.read_text())
    verify_manifest(root, document, paths)
    print(json.dumps({"integrity": "verified", "files": len(paths)}))
