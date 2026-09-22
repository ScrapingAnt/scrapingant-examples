"""Observable HTTP-only plugins for the self-authored local lab."""
import random
from proxy.http.proxy import HttpProxyBasePlugin


class MarkerPlugin(HttpProxyBasePlugin):
    marker = b"local-lab"

    def before_upstream_connection(self, request):
        if not request.is_https_tunnel:
            request.add_header(b"X-Lab-Proxy", self.marker)
        return request


class UpstreamA(MarkerPlugin):
    marker = b"upstream-a"


class UpstreamB(MarkerPlugin):
    marker = b"upstream-b"


class LegacyRotatingProxyPlugin(HttpProxyBasePlugin):
    """Old article recipe, preserved solely to reproduce its failure."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.proxy_list = ['127.0.0.1:8901', '127.0.0.1:8902']

    def before_upstream_connection(self, request):
        proxy = random.choice(self.proxy_list)
        proxy_host, proxy_port = proxy.split(':')
        request.host = proxy_host
        request.port = int(proxy_port)
        return request
