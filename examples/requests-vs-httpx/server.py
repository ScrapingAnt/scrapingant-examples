"""Local test server for the requests vs httpx packet (hypercorn, raw ASGI).

Plain HTTP/1.1 on 127.0.0.1:8080 and [::1]:8080; TLS with ALPN (h2 + http/1.1) on 127.0.0.1:8443 and [::1]:8443
using certs/localhost.pem. Endpoints mirror the httpbin ones the article uses:
  /get, /post, /delay/<seconds>, /bytes/<n>, /status/<code>, /redirect/<n>, /stats, /stats/reset
/stats counts distinct client (host, port) pairs = TCP connections, and requests per path; /stats itself is not counted.
"""
import asyncio
import json
import sys

from hypercorn.asyncio import serve
from hypercorn.config import Config

CONNECTIONS: set[tuple[str, int]] = set()
REQUESTS: dict[str, int] = {}
CHUNK = 64 * 1024


async def read_body(receive) -> bytes:
    body = b""
    while True:
        msg = await receive()
        body += msg.get("body", b"")
        if not msg.get("more_body"):
            return body


async def respond(send, status: int, body: bytes, content_type: str = "application/json", extra=()):
    headers = [(b"content-type", content_type.encode()), (b"content-length", str(len(body)).encode()), *extra]
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        while True:
            msg = await receive()
            if msg["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif msg["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
    if scope["type"] != "http":
        return
    path = scope["path"]
    body = await read_body(receive)
    if path == "/stats":
        return await respond(send, 200, json.dumps({"connections": len(CONNECTIONS), "requests": sum(REQUESTS.values()), "by_path": REQUESTS}).encode())
    if path == "/stats/reset":
        CONNECTIONS.clear(); REQUESTS.clear()
        return await respond(send, 200, b'{"reset": true}')
    CONNECTIONS.add(tuple(scope["client"]))
    REQUESTS[path] = REQUESTS.get(path, 0) + 1
    headers = {k.decode(): v.decode() for k, v in scope["headers"]}
    info = {"http_version": scope["http_version"], "scheme": scope["scheme"], "client_port": scope["client"][1],
            "query": scope["query_string"].decode(), "user_agent": headers.get("user-agent", "")}
    parts = path.strip("/").split("/")
    if path == "/get":
        return await respond(send, 200, json.dumps({"path": path, **info}).encode())
    if path == "/post":
        return await respond(send, 200, json.dumps({"path": path, "content_type": headers.get("content-type", ""), "body": body.decode("utf-8", "replace"), **info}).encode())
    if parts[0] == "delay":
        await asyncio.sleep(float(parts[1]))
        return await respond(send, 200, json.dumps({"path": path, "delayed": float(parts[1]), **info}).encode())
    if parts[0] == "status":
        code = int(parts[1])
        return await respond(send, code, json.dumps({"status": code, **info}).encode())
    if parts[0] == "redirect":
        n = int(parts[1])
        target = "/get" if n <= 1 else f"/redirect/{n - 1}"
        return await respond(send, 302, b"", "text/plain", [(b"location", target.encode())])
    if parts[0] == "bytes":
        n = int(parts[1])
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"application/octet-stream"), (b"content-length", str(n).encode())]})
        sent = 0
        while sent < n:
            size = min(CHUNK, n - sent)
            sent += size
            await send({"type": "http.response.body", "body": b"x" * size, "more_body": sent < n})
        return
    return await respond(send, 404, json.dumps({"error": "not found", "path": path}).encode())


if __name__ == "__main__":
    config = Config()
    config.bind = ["127.0.0.1:8443", "[::1]:8443"]
    config.insecure_bind = ["127.0.0.1:8080", "[::1]:8080"]
    config.certfile = "certs/localhost.pem"
    config.keyfile = "certs/localhost-key.pem"
    config.alpn_protocols = ["h2", "http/1.1"]
    config.keep_alive_timeout = 30
    config.h2_max_concurrent_streams = 200
    config.accesslog = None
    config.errorlog = "-" if "--log" in sys.argv else None
    asyncio.run(serve(app, config))
