import unittest
from scraper import retry_after_seconds


class RetryAfterTests(unittest.TestCase):
    def test_valid_seconds(self):
        self.assertEqual(retry_after_seconds('1', 0), 1)

    def test_http_date(self):
        self.assertEqual(retry_after_seconds('Thu, 01 Jan 1970 00:00:05 GMT', 2), 3)

    def test_past_date(self):
        self.assertEqual(retry_after_seconds('Thu, 01 Jan 1970 00:00:01 GMT', 2), 0)

    def test_invalid_values(self):
        for value in [None, '', 'oops', '-1', '1.5', 'inf']:
            with self.subTest(value=value):
                self.assertIsNone(retry_after_seconds(value, 0))


if __name__ == '__main__':
    unittest.main()
