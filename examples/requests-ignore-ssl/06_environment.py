"""Each case runs in a child process so the environment variable is set before requests is imported."""
import os, subprocess, sys
from _common import URL, CA
CHILD = f"import requests\nfrom _common import show\nshow('requests.get(URL)', lambda: requests.get('{URL}').status_code)\n"
CHILD_NOENV = f"import requests\nfrom _common import show\ns = requests.Session(); s.trust_env = False\nshow('trust_env=False; s.get(URL)', lambda: s.get('{URL}').status_code)\n"
cases = [
    ("REQUESTS_CA_BUNDLE=certs/localhost.pem", {"REQUESTS_CA_BUNDLE": CA}, CHILD),
    ("CURL_CA_BUNDLE=certs/localhost.pem", {"CURL_CA_BUNDLE": CA}, CHILD),
    ("REQUESTS_CA_BUNDLE='' (empty)", {"REQUESTS_CA_BUNDLE": ""}, CHILD),
    ("REQUESTS_CA_BUNDLE=/nonexistent.pem", {"REQUESTS_CA_BUNDLE": "/nonexistent.pem"}, CHILD),
    ("PYTHONHTTPSVERIFY=0", {"PYTHONHTTPSVERIFY": "0"}, CHILD),
    ("REQUESTS_CA_BUNDLE=certs/localhost.pem with Session.trust_env=False", {"REQUESTS_CA_BUNDLE": CA}, CHILD_NOENV),
]
for label, env, code in cases:
    print(f"$ {' '.join(f'{k}={v!r}' for k, v in env.items())} python -c ...")
    out = subprocess.run([sys.executable, "-c", code], env={**os.environ, **env}, capture_output=True, text=True)
    print((out.stdout + out.stderr).strip())
