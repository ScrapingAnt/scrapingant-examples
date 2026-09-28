"""The default, free loopback test. No API call, even with a configured key."""
import argparse
import functools
import json
import platform
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import version
from pathlib import Path
from playwright.sync_api import sync_playwright
from protocol import ResultError, parse_html, parse_marker
from state import CASES, ROOT, score, snippet

class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_args): pass
    def guess_type(self, path):
        mime = super().guess_type(path)
        return mime + '; charset=utf-8' if mime == 'text/html' else mime

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('run_output/local.json'))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(ROOT / 'fixtures')))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    observations = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            browser_version = browser.version
            for case in CASES:
                page = browser.new_page()
                name = 'dynamic-delayed.html' if case == 'delayed' else 'html-tables.html'
                response = page.goto(f'http://127.0.0.1:{server.server_port}/{name}')
                marker = 'sa-extract-' + uuid.uuid4().hex
                awaitable = '(async () => {' + snippet(case, marker) + '})()'
                # This emulates the documented execution contract, not the API network.
                page.evaluate(awaitable)
                html = page.content()
                html_path = args.output.parent / (case + '.html'); html_path.write_text(html)
                result, error = None, None
                try:
                    result = parse_marker(html, marker)
                    assert parse_html(html, marker) == result
                except ResultError as exc:
                    error = str(exc)
                node = subprocess.run(['node', str(ROOT / 'parse-marker.mjs'), str(html_path), marker], capture_output=True, text=True)
                node_matches = (node.returncode == 0 and json.loads(node.stdout) == result) if result is not None else (node.returncode == 1 and node.stderr.strip() == error)
                observations.append({'case': case, 'http_status': response.status, 'marker': marker,
                                     'result': result, 'transport_error': error, 'node_matches': node_matches,
                                     'passed': response.status == 200 and score(case, result, error) and node_matches})
                page.close()
            browser.close()
    finally:
        server.shutdown(); server.server_close(); thread.join()
    report = {'tested_at': datetime.now(timezone.utc).isoformat(), 'python': platform.python_version(),
              'playwright': version('playwright'), 'chromium': browser_version, 'node': subprocess.check_output(['node', '--version'], text=True).strip(),
              'api_requests': 0, 'observations': observations, 'passed': all(row['passed'] for row in observations)}
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'cases': len(observations), 'passed': report['passed'], 'api_requests': 0}))
    return 0 if report['passed'] else 1

if __name__ == '__main__': raise SystemExit(main())
