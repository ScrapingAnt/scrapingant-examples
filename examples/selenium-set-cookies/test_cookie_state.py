import json
import os
import tempfile
import unittest
from pathlib import Path

from cookie_state import save_snapshot, restore_snapshot


class Browser:
    current_url = 'https://catalog.example.test/catalog/'
    def __init__(self, cookies=None):
        self.cookies = cookies or []
        self.added = []
    def get_cookies(self):
        return self.cookies
    def add_cookie(self, cookie):
        self.added.append(cookie)


class CookieStateTests(unittest.TestCase):
    origin = 'https://catalog.example.test'
    cookie = {'name': 'demo_session', 'value': 'synthetic', 'domain': 'catalog.example.test',
              'path': '/catalog/', 'secure': True, 'httpOnly': True, 'sameSite': 'Lax'}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'cookies.json'

    def write(self, cookies, origin=None):
        self.path.write_text(json.dumps({'version': 1, 'origin': origin or self.origin, 'cookies': cookies}))

    def test_round_trip_preserves_attributes_without_broadening_domain(self):
        save_snapshot(Browser([self.cookie]), self.path, self.origin)
        target = Browser()
        result = restore_snapshot(target, self.path, self.origin, now=100)
        self.assertEqual(result, {'restored': 1, 'skipped_expired': 0})
        self.assertEqual(target.added, [{k: v for k, v in self.cookie.items() if k != 'domain'}])

    def test_expired_is_skipped_session_cookie_is_kept(self):
        self.write([dict(self.cookie, expiry=100), self.cookie])
        target = Browser()
        self.assertEqual(restore_snapshot(target, self.path, self.origin, now=100),
                         {'restored': 1, 'skipped_expired': 1})

    def test_origin_mismatch_fails_before_insertion(self):
        self.write([self.cookie], 'https://other.example.test')
        target = Browser()
        with self.assertRaises(ValueError): restore_snapshot(target, self.path, self.origin)
        self.assertEqual(target.added, [])

    def test_redirect_to_other_origin_fails_before_insertion(self):
        self.write([self.cookie])
        target = Browser(); target.current_url = 'https://login.example.test/'
        with self.assertRaises(ValueError): restore_snapshot(target, self.path, self.origin)
        self.assertEqual(target.added, [])

    def test_foreign_or_parent_domain_is_not_accepted_by_substring(self):
        for domain in ['evilcatalog.example.test', 'example.test', 'catalog.example.test.evil.test']:
            with self.subTest(domain=domain):
                self.write([self.cookie, dict(self.cookie, domain=domain)])
                target = Browser()
                with self.assertRaises(ValueError): restore_snapshot(target, self.path, self.origin)
                self.assertEqual(target.added, [])

    def test_invalid_cookie_data_fails_before_any_insertion(self):
        for change in [{'expiry': 'tomorrow'}, {'expiry': True}, {'sameSite': 'unknown'},
                       {'value': 'a;b=c'}, {'path': 'catalog'}, {'httpOnly': 'false'}]:
            with self.subTest(change=change):
                self.write([self.cookie, dict(self.cookie, **change)])
                target = Browser()
                with self.assertRaises(ValueError): restore_snapshot(target, self.path, self.origin)
                self.assertEqual(target.added, [])

    @unittest.skipUnless(os.name == 'posix', 'POSIX file modes')
    def test_file_is_owner_read_write_even_if_it_already_existed(self):
        self.path.write_text('old'); self.path.chmod(0o644)
        save_snapshot(Browser([self.cookie]), self.path, self.origin)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    @unittest.skipUnless(hasattr(os, 'O_NOFOLLOW'), 'requires O_NOFOLLOW')
    def test_save_refuses_symlink(self):
        target = Path(self.tmp.name) / 'other'; target.write_text('unchanged')
        self.path.symlink_to(target)
        with self.assertRaises(OSError): save_snapshot(Browser([self.cookie]), self.path, self.origin)
        self.assertEqual(target.read_text(), 'unchanged')


if __name__ == '__main__':
    unittest.main()
