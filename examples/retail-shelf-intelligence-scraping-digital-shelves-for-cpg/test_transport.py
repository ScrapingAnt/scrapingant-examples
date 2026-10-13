"""All requests are owned loopback or in-memory delegates; no provider calls."""
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import threading
import unittest
from urllib.parse import parse_qs, urlsplit

import collector

BODY = (Path(__file__).parent / "fixtures/baseline.html").read_bytes()
KEY = "owned-test-key-NEVER-A-CREDENTIAL"


class Response(BytesIO):
    def __init__(self, body=BODY, headers=None, status=200, url="https://api.scrapingant.com/v2/general"):
        super().__init__(body)
        self.status = status
        self.headers = Message()
        for name, value in (headers if headers is not None else [
            ("Ant-page-status-code", "200"),
            ("Ant-original-header-content-type", "text/html; charset=utf-8"),
            ("Ant-credits-cost", "1")]):
            self.headers.add_header(name, value)
        self.url = url

    def geturl(self):
        return self.url


def managed(response):
    def send(request, timeout):
        response.url = request.full_url
        return response
    return collector.acquire(collector.SOURCE, managed=True, key=KEY,
                             send=send)


class Managed(unittest.TestCase):
    def test_explicit_header_auth_and_request_settings(self):
        captured = []
        def send(request, timeout):
            captured.append((request, timeout))
            return Response(url=request.full_url)
        receipt = collector.acquire(collector.SOURCE, managed=True, browser=True, key=KEY, send=send)
        self.assertEqual(len(captured), 1)
        request, timeout = captured[0]
        self.assertEqual(request.get_header("X-api-key"), KEY)
        self.assertNotIn(KEY, request.full_url)
        self.assertEqual(parse_qs(urlsplit(request.full_url).query), {
            "url":[collector.SOURCE], "browser":["true"], "proxy_type":["datacenter"],
            "proxy_country":["us"], "return_page_source":["false"], "timeout":["30"]})
        self.assertEqual(timeout, 30)
        self.assertEqual(receipt["receipt"]["actual_receipt_credits"], 1)

    def test_raw_mode_is_explicit_and_has_no_automatic_render_retry(self):
        captured = []
        def send(request, timeout):
            captured.append(request)
            return Response(body=b'<html>blocked</html>', status=423, url=request.full_url)
        result = collector.acquire(collector.SOURCE, managed=True, key=KEY, send=send)
        self.assertEqual(len(captured), 1)
        self.assertEqual(parse_qs(urlsplit(captured[0].full_url).query)["browser"], ["false"])
        self.assertFalse(result["usable"])

    def test_actual_target_status_is_required(self):
        for status in (None, "404", "200.0", "unknown"):
            with self.subTest(status=status):
                headers = [("Ant-credits-cost", "10"), ("Ant-original-header-content-type", "text/html")]
                if status is not None:
                    headers.append(("Ant-page-status-code", status))
                result = managed(Response(headers=headers))
                self.assertFalse(result["usable"])
                self.assertEqual(result["receipt"]["actual_receipt_credits"], 10)

    def test_actual_original_target_media_is_used_without_outer_type(self):
        result = managed(Response())
        self.assertTrue(result["usable"])
        self.assertEqual(result["receipt"]["target_media_type"], "text/html")

    def test_nonhtml_and_missing_target_media_are_rejected(self):
        for media in (None, "application/json", "image/png"):
            with self.subTest(media=media):
                headers = [("Ant-page-status-code", "200"), ("Ant-credits-cost", "1"), ("Content-Type", "text/html")]
                if media:
                    headers.append(("Ant-original-header-content-type", media))
                result = managed(Response(headers=headers))
                self.assertFalse(result["usable"])

    def test_unknown_and_malformed_credit_cost_remain_unknown(self):
        for credits in (None, "", "NaN", "-1", "1.5", "1,10"):
            with self.subTest(credits=credits):
                headers = [("Ant-page-status-code", "200"), ("Ant-original-header-content-type", "text/html")]
                if credits is not None:
                    headers.append(("Ant-credits-cost", credits))
                result = managed(Response(headers=headers))
                self.assertTrue(result["usable"])
                self.assertIsNone(result["receipt"]["actual_receipt_credits"])
                self.assertEqual(result["receipt"]["credit_receipt_state"], "unknown")

    def test_duplicate_headers_do_not_create_fake_target_or_cost_acceptance(self):
        for name in ("Ant-page-status-code", "Ant-original-header-content-type", "Ant-credits-cost"):
            with self.subTest(name=name):
                response = Response()
                response.headers.add_header(name, "200" if name.endswith("code") else "1")
                result = managed(response)
                if name == "Ant-credits-cost":
                    self.assertIsNone(result["receipt"]["actual_receipt_credits"])
                else:
                    self.assertFalse(result["usable"])

    def test_api_failure_receipt_is_separate_from_target_success(self):
        result = managed(Response(status=503))
        self.assertFalse(result["usable"])
        self.assertEqual(result["receipt"]["api_http_status"], 503)
        self.assertEqual(result["receipt"]["target_http_status"], 200)
        self.assertEqual(result["receipt"]["actual_receipt_credits"], 1)

    def test_body_and_encoded_key_echoes_never_leave_observer(self):
        echoes = [KEY, ''.join('&#%d;' % ord(c) for c in KEY),
                  ''.join('%%%02X' % ord(c) for c in KEY),
                  ''.join('\\u%04x' % ord(c) for c in KEY)]
        for echo in echoes:
            with self.subTest(echo=echo):
                result = managed(Response(body=BODY + echo.encode()))
                self.assertFalse(result["usable"])
                self.assertEqual(result["body"], b"")
                self.assertNotIn(KEY, json.dumps(result["receipt"]))

    def test_error_message_key_echo_is_not_logged_and_no_retry_occurs(self):
        calls = []
        def fail(request, timeout):
            calls.append(request)
            raise OSError("credential " + KEY)
        result = collector.acquire(collector.SOURCE, managed=True, key=KEY, send=fail)
        self.assertEqual(len(calls), 1)
        self.assertFalse(result["usable"])
        self.assertNotIn(KEY, json.dumps(result["receipt"]))
        self.assertIsNone(result["receipt"]["actual_receipt_credits"])

    def test_header_key_echo_is_not_serialized_in_media_receipt(self):
        result = managed(Response(headers=[("Ant-page-status-code","200"),
            ("Ant-original-header-content-type","text/html; echoed=" + KEY), ("Ant-credits-cost","1")]))
        self.assertFalse(result["usable"])
        self.assertNotIn(KEY, json.dumps(result["receipt"]))
        self.assertEqual(result["body"], b"")

    def test_API_redirect_response_is_rejected_without_retry(self):
        calls = []
        def send(request, timeout):
            calls.append(request)
            return Response(status=302, url=request.full_url)
        result = collector.acquire(collector.SOURCE, managed=True, key=KEY, send=send)
        self.assertFalse(result["usable"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["receipt"]["api_http_status"], 302)

    def test_credentials_in_target_URL_are_rejected_before_dispatch(self):
        calls = []
        for url in ("https://example.test/?key=" + KEY, "https://user:password@example.test/", "file:///tmp/example"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                collector.acquire(url, managed=True, key=KEY, send=lambda *a: calls.append(a))
        self.assertEqual(calls, [])

    def test_missing_key_fails_before_any_dispatch(self):
        calls = []
        with self.assertRaises(ValueError):
            collector.acquire(collector.SOURCE, managed=True, key="", send=lambda *a: calls.append(a))
        self.assertEqual(calls, [])

    def test_oversized_response_is_not_retained_but_credits_are(self):
        result = managed(Response(body=b'x' * 262145))
        self.assertFalse(result["usable"])
        self.assertEqual(result["body"], b"")
        self.assertEqual(result["receipt"]["actual_receipt_credits"], 1)

    def test_elapsed_read_deadline_cannot_be_mislabeled_success(self):
        ticks = iter([0, 0, 31])
        result = collector.acquire(collector.SOURCE, managed=True, key=KEY,
                                   send=lambda request, timeout: Response(url=request.full_url), clock=lambda: next(ticks, 31))
        self.assertFalse(result["usable"])
        self.assertEqual(result["receipt"]["error"], "read_deadline")


class Loopback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                cls.paths.append(self.path)
                status, media, body = {
                    "/good": (200, "text/html", BODY),
                    "/failure": (503, "text/html", b"service unavailable"),
                    "/nonhtml": (200, "application/json", b'{}'),
                    "/big": (200, "text/html", b'x' * 262145),
                    "/redirect": (302, "text/html", b'redirect')
                }.get(self.path, (404, "text/html", b'missing'))
                self.send_response(status)
                self.send_header("Content-Type", media)
                self.send_header("Content-Length", str(len(body)))
                if self.path == "/redirect":
                    self.send_header("Location", "/good")
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            def log_message(self, *args):
                pass
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:%d" % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_direct_owned_html_receipt_has_no_provider_charge(self):
        result = collector.acquire(self.base + "/good")
        self.assertTrue(result["usable"])
        self.assertEqual(result["body"], BODY)
        self.assertIsNone(result["receipt"]["api_http_status"])
        self.assertEqual(result["receipt"]["target_http_status"], 200)
        self.assertEqual(result["receipt"]["credit_receipt_state"], "not_applicable")

    def test_failure_nonhtml_and_oversize_do_not_reach_parser(self):
        for path in ("/failure", "/nonhtml", "/big"):
            with self.subTest(path=path):
                result = collector.acquire(self.base + path)
                self.assertFalse(result["usable"])
                self.assertEqual(result["body"], b"")

    def test_direct_redirect_is_not_followed(self):
        start = len(self.paths)
        result = collector.acquire(self.base + "/redirect")
        self.assertFalse(result["usable"])
        self.assertEqual(self.paths[start:], ["/redirect"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
