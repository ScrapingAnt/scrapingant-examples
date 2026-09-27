"""LWP jar persistence with deliberate session opt-in; snapshots are credentials."""
import copy
from http.cookiejar import LWPCookieJar
import os
from pathlib import Path
import stat


def save_private_jar(jar, path, *, include_session=False):
    """Save a new owner-only file. Never overwrite or save expired entries.

    Discard/session cookies are excluded unless the caller explicitly opts in.
    The destination must be a private location; this format is not encrypted.
    """
    lwp = LWPCookieJar()
    for cookie in jar:
        lwp.set_cookie(copy.copy(cookie))
    contents = "#LWP-Cookies-2.0\n" + lwp.as_lwp_str(
        ignore_discard=include_session, ignore_expires=False
    )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(contents)


def load_jar(path, *, include_session=False):
    """Load unexpired cookies; opt in separately to restoring session cookies."""
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("Snapshot must be a regular file")
    if os.name == "posix" and stat.S_IMODE(info.st_mode) & 0o077:
        raise PermissionError("Snapshot must be readable only by its owner")
    jar = LWPCookieJar(str(path))
    jar.load(ignore_discard=include_session, ignore_expires=False)
    return jar
