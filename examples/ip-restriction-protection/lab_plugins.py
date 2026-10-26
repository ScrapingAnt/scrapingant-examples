"""proxy.py plugin that stamps plain-HTTP requests with the proxy's name, so the origin can show which proxy carried them."""
from proxy.http.proxy import HttpProxyBasePlugin


class Marker(HttpProxyBasePlugin):
    marker = b"proxy"

    def before_upstream_connection(self, request):
        if not request.is_https_tunnel:
            request.add_header(b"X-Lab-Proxy", self.marker)
        return request


class AuthProxy(Marker):
    marker = b"auth-proxy-8899"


class ProxyA(Marker):
    marker = b"proxy-a-8901"


class ProxyB(Marker):
    marker = b"proxy-b-8902"
