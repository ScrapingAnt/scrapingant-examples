"""Boundary tests for the explicit LWP persistence policy."""
import os
from pathlib import Path
import stat
import tempfile
import time
import unittest
from http.cookiejar import LWPCookieJar
from requests import Request, Session
from requests.cookies import RequestsCookieJar, create_cookie
from cookie_state import save_private_jar, load_jar


def sample_jar():
    jar = RequestsCookieJar()
    jar.set_cookie(create_cookie("sid", "synthetic-session", domain="127.0.0.1", path="/", rest={"HttpOnly": None}, discard=True))
    jar.set_cookie(create_cookie("region", "EUR", domain="127.0.0.1", path="/catalog/eu", expires=int(time.time()) + 3600, discard=False))
    jar.set_cookie(create_cookie("region", "USD", domain="127.0.0.1", path="/catalog/us", expires=int(time.time()) + 3600, discard=False))
    return jar


class PersistenceTests(unittest.TestCase):
    def test_explicit_session_opt_in_keeps_duplicate_names_and_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cookies.lwp"
            save_private_jar(sample_jar(), path, include_session=True)
            jar = load_jar(path, include_session=True)
            with Session() as session:
                session.trust_env = False
                session.cookies = jar
                eu = session.prepare_request(Request("GET", "http://127.0.0.1/catalog/eu/products"))
                us = session.prepare_request(Request("GET", "http://127.0.0.1/catalog/us/products"))
            self.assertIn("region=EUR", eu.headers["Cookie"])
            self.assertNotIn("region=USD", eu.headers["Cookie"])
            self.assertIn("region=USD", us.headers["Cookie"])
            self.assertNotIn("region=EUR", us.headers["Cookie"])
            self.assertIn("sid=synthetic-session", eu.headers["Cookie"])
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_defaults_do_not_persist_session_cookies(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cookies.lwp"
            save_private_jar(sample_jar(), path)
            self.assertEqual(sorted(c.name for c in load_jar(path)), ["region", "region"])

    def test_load_requires_session_opt_in_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cookies.lwp"
            save_private_jar(sample_jar(), path, include_session=True)
            self.assertEqual(len(load_jar(path)), 2)
            self.assertEqual(len(load_jar(path, include_session=True)), 3)

    def test_expired_entries_excluded_on_save_and_load(self):
        jar = sample_jar()
        jar.set_cookie(create_cookie("expired", "synthetic-expired", domain="127.0.0.1", expires=int(time.time()) - 60, discard=False))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cookies.lwp"
            save_private_jar(jar, path, include_session=True)
            self.assertNotIn("expired", [c.name for c in load_jar(path, include_session=True)])
            # Independently produce a file containing an expired entry to test loading.
            legacy = LWPCookieJar()
            for cookie in jar:
                legacy.set_cookie(cookie)
            legacy.save(str(path), ignore_discard=True, ignore_expires=True)
            self.assertNotIn("expired", [c.name for c in load_jar(path, include_session=True)])

    def test_secure_and_httponly_metadata_survive_without_browser_claim(self):
        jar = sample_jar()
        jar.set_cookie(create_cookie("secure_demo", "synthetic", domain="127.0.0.1", secure=True, rest={"HttpOnly": None, "SameSite": "Lax"}))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cookies.lwp"
            save_private_jar(jar, path, include_session=True)
            restored = next(c for c in load_jar(path, include_session=True) if c.name == "secure_demo")
            self.assertTrue(restored.secure)
            self.assertTrue(restored.has_nonstandard_attr("HttpOnly"))
            self.assertEqual(restored.get_nonstandard_attr("SameSite"), "Lax")
            with Session() as session:
                session.trust_env = False
                session.cookies.set_cookie(restored)
                prepped = session.prepare_request(Request("GET", "http://127.0.0.1/"))
                self.assertNotIn("Cookie", prepped.headers)

    def test_refuses_overwrite_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cookies.lwp"
            path.write_text("do not replace")
            with self.assertRaises(FileExistsError):
                save_private_jar(sample_jar(), path)
            self.assertEqual(path.read_text(), "do not replace")
            link = Path(tmp) / "link.lwp"
            link.symlink_to(path)
            with self.assertRaises(FileExistsError):
                save_private_jar(sample_jar(), link)

    @unittest.skipUnless(os.name == "posix", "POSIX file mode policy")
    def test_refuses_group_readable_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cookies.lwp"
            save_private_jar(sample_jar(), path)
            path.chmod(0o644)
            with self.assertRaises(PermissionError):
                load_jar(path)


if __name__ == "__main__":
    unittest.main()
