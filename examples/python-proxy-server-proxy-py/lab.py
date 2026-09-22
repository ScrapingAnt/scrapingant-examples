"""Local forward-proxy evidence. No external targets, credentials or trust changes."""
import collections
import contextlib
import http.server
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shlex
import signal
import socket
import ssl
import subprocess
import sys
import threading
import time

import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'expected_output'
GENERATED = ROOT / 'generated'
ENV = {k: v for k, v in os.environ.items() if k.lower() not in
       {'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy'}}
ENV['PYTHONPATH'] = str(ROOT)
EVENTS = []
LOCK = threading.Lock()


def command(args, *, allowed=(0,), show=True):
    args = [str(a) for a in args]
    if show:
        print('$ ' + shlex.join(args), flush=True)
    result = subprocess.run(args, cwd=ROOT, env=ENV, capture_output=True,
                            text=True, timeout=20)
    if show:
        print(result.stdout, end='')
        print(result.stderr, end='')
        print(f'exit={result.returncode}', flush=True)
    assert result.returncode in allowed, result.stderr
    return result


class Origin(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        data = {'origin': 'proxy-py-local-fixture', 'path': self.path,
                'marker': self.headers.get('X-Lab-Proxy'),
                'tls': isinstance(self.connection, ssl.SSLSocket)}
        body = (json.dumps(data, sort_keys=True) + '\n').encode()
        with LOCK:
            EVENTS.append(data)
            with (OUT / 'origin.jsonl').open('a') as log:
                log.write(body.decode())
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def certificates():
    GENERATED.mkdir(exist_ok=True)
    commands = [
        ['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '2',
         '-subj', '/CN=Proxy Lab CA', '-keyout', 'generated/ca.key', '-out', 'generated/ca.pem'],
        ['openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-config', 'fixtures/server.cnf',
         '-keyout', 'generated/server.key', '-out', 'generated/server.csr'],
        ['openssl', 'x509', '-req', '-in', 'generated/server.csr', '-CA', 'generated/ca.pem',
         '-CAkey', 'generated/ca.key', '-CAcreateserial', '-days', '2',
         '-extfile', 'fixtures/server.cnf', '-extensions', 'server', '-out', 'generated/server.pem'],
    ]
    with (OUT / 'certificates.txt').open('w') as log:
        for args in commands:
            result = command(args, show=False)
            log.write('$ ' + shlex.join(args) + '\n' + result.stdout + result.stderr + '\nexit=0\n')


@contextlib.contextmanager
def lab():
    OUT.mkdir(exist_ok=True)
    (OUT / 'origin.jsonl').write_text('')
    EVENTS.clear()
    certificates()
    servers, children, handles = [], [], []
    def proxy(name, port, *extra):
        args = [sys.executable, '-m', 'proxy', '--hostname', '127.0.0.1', '--port', str(port),
                '--num-workers', '1', '--num-acceptors', '1', '--log-level', 'INFO', *extra]
        print('$ ' + shlex.join(args), flush=True)
        handle = (OUT / (name + '.log')).open('w')
        handles.append(handle)
        child = subprocess.Popen(args, cwd=ROOT, env=ENV, stdout=handle,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        children.append(child)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise RuntimeError(f'{name} exited {child.returncode}: see {handle.name}')
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.2):
                    pass
                return
            except OSError:
                time.sleep(.05)
        raise TimeoutError(name)
    try:
        for port, tls in [(8000, False), (8443, True)]:
            server = http.server.ThreadingHTTPServer(('127.0.0.1', port), Origin)
            servers.append(server)
            if tls:
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.load_cert_chain(GENERATED / 'server.pem', GENERATED / 'server.key')
                server.socket = ctx.wrap_socket(server.socket, server_side=True)
            threading.Thread(target=server.serve_forever, daemon=True).start()
        proxy('plain', 8899)
        proxy('auth', 8900, '--basic-auth', 'lab:secret')
        proxy('upstream-a', 8901, '--plugins', 'lab_plugins.UpstreamA')
        proxy('upstream-b', 8902, '--plugins', 'lab_plugins.UpstreamB')
        proxy('pool', 8903, '--plugins', 'proxy.plugin.ProxyPoolPlugin',
              '--proxy-pool', '127.0.0.1:8901', '--proxy-pool', '127.0.0.1:8902')
        proxy('marker', 8904, '--plugins', 'lab_plugins.MarkerPlugin')
        proxy('legacy', 8905, '--plugins', 'lab_plugins.LegacyRotatingProxyPlugin')
        yield
    finally:
        for child in reversed(children):
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGINT)
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=5)
        for server in servers:
            server.shutdown()
            server.server_close()
        for handle in handles:
            handle.close()


def curl(case, *, tls=False, port=8899, credentials=None, allowed=(0,)):
    url = f'{"https" if tls else "http"}://localhost:{8443 if tls else 8000}/{case}'
    args = ['curl', '--noproxy', '', '--silent', '--show-error', '--fail', '--verbose',
            '--max-time', '5', '--proxy', f'http://127.0.0.1:{port}']
    if credentials:
        args += ['--proxy-user', credentials]
    if tls:
        args += ['--cacert', 'generated/ca.pem']
    result = command(args + [url], allowed=allowed)
    if result.returncode == 0:
        data = json.loads(result.stdout)
        assert data['origin'] == 'proxy-py-local-fixture' and data['path'] == '/' + case
        assert data['tls'] == tls
        if tls:
            assert '200 Connection established' in result.stderr
        return data
    return result


def request(case, *, tls=False, port=8899, credentials=None, error=False, host='localhost'):
    upstream = f'http://{credentials + "@" if credentials else ""}127.0.0.1:{port}'
    url = f'{"https" if tls else "http"}://{host}:{8443 if tls else 8000}/{case}'
    print(f'Requests GET {url} proxies={{http: {upstream}, https: {upstream}}} trust_env=False timeout=5', flush=True)
    with requests.Session() as session:
        session.trust_env = False
        try:
            response = session.get(url, proxies={'http': upstream, 'https': upstream},
                                   verify=str(GENERATED / 'ca.pem'), timeout=5)
            print(f'status={response.status_code} body={response.text.strip()}', flush=True)
            if error:
                assert response.status_code == 407
                return
            response.raise_for_status()
            data = response.json()
            assert data['origin'] == 'proxy-py-local-fixture' and data['path'] == '/' + case
            assert data['tls'] == tls
            return data
        except requests.exceptions.ProxyError as exc:
            print(f'{type(exc).__name__}: {exc}', flush=True)
            assert error and tls and '407' in str(exc)


def test():
    print('Environment:', platform.platform(), sys.version)
    for name in ['proxy.py', 'requests', 'certifi', 'charset-normalizer', 'idna', 'urllib3']:
        print(name, importlib.metadata.version(name))
    command(['curl', '--version'])
    command(['openssl', 'version'])
    (OUT / 'proxy-help.txt').write_text(command([sys.executable, '-m', 'proxy', '--help'], show=False).stdout)
    with lab():
        command([sys.executable, 'client.py', 'http'])
        command([sys.executable, 'client.py', 'https'])
        for tls in [False, True]:
            curl('curl-' + str(tls), tls=tls)
            request('requests-' + str(tls), tls=tls)
            curl('auth-curl-' + str(tls), tls=tls, port=8900, credentials='lab:secret')
            request('auth-requests-' + str(tls), tls=tls, port=8900, credentials='lab:secret')
            for credentials in [None, 'lab:wrong']:
                case = f'rejected-{tls}-{credentials}'
                before = len(EVENTS)
                result = curl(case, tls=tls, port=8900, credentials=credentials, allowed=(22, 56))
                assert '407' in result.stderr
                request('requests-' + case, tls=tls, port=8900, credentials=credentials, error=True)
                assert len(EVENTS) == before, 'Rejected request reached origin'
        assert curl('marker', port=8904)['marker'] == 'local-lab'
        assert curl('marker-tunnel', port=8904, tls=True)['marker'] is None
        for port, marker in [(8901, 'upstream-a'), (8902, 'upstream-b')]:
            assert curl('individual-' + marker, port=port)['marker'] == marker
        counts = collections.Counter()
        for index in range(20):
            data = request(f'pool-{index}', port=8903)
            assert data['marker'] in {'upstream-a', 'upstream-b'}
            counts[data['marker']] += 1
        print('POOL: ' + json.dumps(dict(counts), sort_keys=True) + '; correct destinations=20/20')
        # Pool selection is random; do not fail merely because one endpoint is not selected.
        assert request('private-ip-bypass', port=8903, host='127.0.0.1')['marker'] is None
        curl('pool-tunnel', port=8903, tls=True)
        before = len(EVENTS)
        curl('legacy', port=8905, allowed=(22, 52, 56))
        assert len(EVENTS) == before
        # Release a locally allocated port, then immediately probe it; unexpected reuse fails this assertion.
        with socket.socket() as blocked:
            blocked.bind(('127.0.0.1', 0))
            unavailable_port = blocked.getsockname()[1]
        curl('refused', port=unavailable_port, allowed=(7,))
        command([sys.executable, '-m', 'proxy', '--hostname', '127.0.0.1', '--port', '8899',
                 '--num-workers', '1', '--num-acceptors', '1'], allowed=(1,))
        # Flush access logs after clients close; output and log assertions run after teardown.
    assert 'CONNECT localhost:8443' in (OUT / 'plain.log').read_text()
    assert '400 BAD REQUEST' in (OUT / 'legacy.log').read_text()
    for item in EVENTS:
        if item['path'].startswith('/pool-') and item['marker']:
            assert item['path'] + ' ' in (OUT / (item['marker'] + '.log')).read_text()
    for name, marker in [('upstream-a', 'upstream-a'), ('upstream-b', 'upstream-b')]:
        assert 'individual-' + marker in (OUT / (name + '.log')).read_text()
    summary = {'forwarding_successes': 4, 'authenticated_successes': 4,
               'rejected_requests': 8, 'rejected_origin_hits': 0,
               'pool_correct_destinations': 20, 'pool_requests': 20, 'pool_counts': dict(counts),
               'origin_requests': len(EVENTS)}
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print('PASS ' + json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    os.chdir(ROOT)
    if len(sys.argv) == 2 and sys.argv[1] == 'serve':
        with lab():
            print('READY: origin 8000/8443; proxy 8899; auth 8900; pool 8903; marker 8904. Ctrl-C stops this lab.', flush=True)
            try:
                threading.Event().wait()
            except KeyboardInterrupt:
                pass
    else:
        test()
