"""Verification for a known payload in an isolated local download directory."""
import hashlib
from pathlib import Path
import time


def ensure_empty(directory):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.iterdir()):
        raise FileExistsError(f"Use an empty download directory: {directory}")
    return directory


def wait_for_download(target, expected_size, expected_sha256, timeout=30, poll=0.1):
    target = Path(target)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        partials = [p for p in target.parent.iterdir()
                    if p.suffix in {".crdownload", ".part"}]
        if target.is_file() and not partials:
            try:
                payload = target.read_bytes()
            except FileNotFoundError:  # Browser renamed a file between checks.
                continue
            if len(payload) == expected_size:
                if hashlib.sha256(payload).hexdigest() != expected_sha256:
                    raise ValueError(f"Checksum mismatch: {target.name}")
                return target
        time.sleep(poll)
    names = sorted(p.name for p in target.parent.iterdir())
    raise TimeoutError(f"Not verified: {target.name}; directory entries: {names}")
