"""Standard age authenticated encryption and durable readback; no network.

Only a public age recipient is used by Actions. The private identity stays on
the owner's local filesystem. An approval can be returned only after decrypted
JSON passes caller validation and its exact bytes survive fsync and readback.
No provider secret is inherited by the age subprocess, and errors are fixed.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

MAX_PLAINTEXT_BYTES = 8388608
MAX_CIPHERTEXT_BYTES = MAX_PLAINTEXT_BYTES + 65536


class TransportError(Exception):
    def __init__(self):
        super().__init__('encrypted_evidence_transport_failed')


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def checked_hash(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def json_payload(blob):
    if not isinstance(blob, bytes) or not 1 <= len(blob) <= MAX_PLAINTEXT_BYTES:
        raise TransportError()
    try:
        def unique_pairs(pairs):
            value={}
            for key,item in pairs:
                if key in value:raise ValueError()
                value[key]=item
            return value
        def reject_constant(_):raise ValueError()
        def finite_float(number):
            value=float(number)
            if not math.isfinite(value):raise ValueError()
            return value
        value = json.loads(blob,object_pairs_hook=unique_pairs,parse_constant=reject_constant,
                           parse_float=finite_float)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise TransportError() from None


def crypto(binary, arguments, blob):
    try:
        executable = Path(binary)
        if not executable.is_absolute() or executable.is_symlink() or not executable.is_file():
            raise ValueError()
        result = subprocess.run([str(executable), *arguments], input=blob,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=15,
            env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
        if result.returncode != 0 or not result.stdout:
            raise ValueError()
        return result.stdout
    except (OSError, ValueError, subprocess.SubprocessError):
        raise TransportError() from None


def durable_write(path, blob):
    """Atomic0600 file, file+directory fsync, exact-size/hash readback."""
    destination = Path(path)
    temporary = None
    try:
        if destination.is_symlink() or not destination.parent.is_dir():
            raise ValueError()
        fd, temporary = tempfile.mkstemp(prefix='.study-capture-', dir=destination.parent)
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(blob)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        temporary = None
        directory = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        if destination.read_bytes() != blob or destination.stat().st_mode & 0o777 != 0o600:
            raise ValueError()
    except (OSError, ValueError):
        raise TransportError() from None
    finally:
        if temporary:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def encrypt_capture(payload, destination, binary, recipient):
    json_payload(payload)
    if not isinstance(recipient, str) or re.fullmatch(r'age1[a-z0-9]{58}', recipient) is None:
        raise TransportError()
    cipher = crypto(binary, ['--encrypt', '--recipient', recipient], payload)
    if not cipher.startswith(b'age-encryption.org/v1\n') or len(cipher) > MAX_CIPHERTEXT_BYTES:
        raise TransportError()
    durable_write(destination, cipher)
    return {'plaintext_sha256': digest(payload), 'ciphertext_sha256': digest(cipher),
            'remote_file_readback_verified': True}


def decrypt_and_verify(cipher, destination, binary, identity, plaintext_sha256,
                       ciphertext_sha256, *, validate_payload=None):
    if (not isinstance(cipher, bytes) or not 1 <= len(cipher) <= MAX_CIPHERTEXT_BYTES
            or not checked_hash(plaintext_sha256) or not checked_hash(ciphertext_sha256)
            or digest(cipher) != ciphertext_sha256 or not callable(validate_payload)):
        raise TransportError()
    key = Path(identity)
    try:
        info = key.lstat()
        if (key.is_symlink() or not stat.S_ISREG(info.st_mode)
                or info.st_mode & 0o777 != 0o600 or info.st_uid != os.getuid()):
            raise ValueError()
    except (OSError, ValueError):
        raise TransportError() from None
    payload = crypto(binary, ['--decrypt', '--identity', str(key)], cipher)
    value = json_payload(payload)
    try:
        if digest(payload) != plaintext_sha256 or validate_payload(value) is not True:
            raise ValueError()
    except Exception:
        raise TransportError() from None
    durable_write(destination, payload)
    return {'plaintext_sha256': plaintext_sha256, 'ciphertext_sha256': ciphertext_sha256,
            'scope_approved': True}
