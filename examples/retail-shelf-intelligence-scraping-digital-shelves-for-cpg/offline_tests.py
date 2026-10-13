"""Run this packet's actual suite; reject any external DNS/socket attempt."""
import sys
import unittest

attempts = []

def offline_only(event, args):
    host = args[0] if event == "socket.getaddrinfo" else args[1][0] if event == "socket.connect" else None
    if host is not None and host not in ("127.0.0.1", "localhost", "::1"):
        attempts.append(event)
        raise OSError("offline_runner_rejects_external_network")

sys.addaudithook(offline_only)
result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(".", pattern="test_*.py"))
print(f"External DNS/socket attempts blocked: {len(attempts)}")
sys.exit(0 if result.wasSuccessful() and not attempts else 1)
