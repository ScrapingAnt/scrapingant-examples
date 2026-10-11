"""Documented HTML transport. Default evidence runner never calls it live."""
import os
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError, URLError

from collector import CollectionError, MAX_BODY_BYTES, NoRedirect

ENDPOINT = "https://api.scrapingant.com/v2/general"


def build_request(target_url, *, browser, key=None):
    parts = urlsplit(target_url)
    if (parts.scheme != "https" or not parts.netloc or parts.username or
            parts.password or parts.fragment):
        raise ValueError("managed target must be an approved public HTTPS URL")
    if browser not in ("false", "true"):
        raise ValueError("browser must be explicit false or true")
    key = key if key is not None else os.environ["SCRAPINGANT_API_KEY"]
    if not key or "\n" in key or "\r" in key:
        raise ValueError("invalid API key")
    parameters = {"url": target_url, "browser": browser, "proxy_type": "datacenter",
                  "proxy_country": "us", "timeout": "30", "return_page_source": "false"}
    # Keep the secret out of query strings and request URL logs.
    return Request(ENDPOINT + "?" + urlencode(parameters), headers={"x-api-key": key})


def managed_html(target_url, *, browser, opener=None):
    request = build_request(target_url, browser=browser)
    opener = opener or build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=35) as response:
            if response.status != 200:
                raise CollectionError(f"api_http_{response.status}")
            # API success and target success are separate acceptance conditions.
            if response.headers.get("Ant-page-status-code") != "200":
                raise CollectionError("target_status_unaccepted")
            # General response wrappers need not carry an outer media type.
            # Use the documented original-target header when present; unknown
            # target media type is deferred to the collector's listing schema.
            target_type = response.headers.get("Ant-original-header-content-type")
            if target_type is not None and target_type.split(";", 1)[0].strip().lower() != "text/html":
                raise CollectionError("not_html")
            data = response.read(MAX_BODY_BYTES + 1)
            if len(data) > MAX_BODY_BYTES:
                raise CollectionError("body_limit")
            try:
                return data.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                raise CollectionError("invalid_utf8") from None
    except HTTPError as error:
        # Never surface URL or response text; either can carry sensitive values.
        raise CollectionError(f"api_http_{error.code}") from None
    except (URLError, TimeoutError):
        raise CollectionError("api_transport_failed") from None
