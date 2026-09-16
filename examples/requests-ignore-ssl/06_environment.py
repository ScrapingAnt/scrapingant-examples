"""Each case is a real shell command line, run through bash, so the variable is set before Python starts."""
import subprocess
cases = [
    "REQUESTS_CA_BUNDLE=certs/localhost.pem python env_check.py",
    "CURL_CA_BUNDLE=certs/localhost.pem python env_check.py",
    "REQUESTS_CA_BUNDLE='' python env_check.py",
    "REQUESTS_CA_BUNDLE=/nonexistent.pem python env_check.py",
    "PYTHONHTTPSVERIFY=0 python env_check.py",
    "REQUESTS_CA_BUNDLE=certs/localhost.pem python env_check.py --no-trust-env",
]
for cmd in cases:
    print(f"$ {cmd}")
    out = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
    print((out.stdout + out.stderr).strip())
