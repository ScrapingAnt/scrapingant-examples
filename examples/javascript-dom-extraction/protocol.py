"""Read a deliberately narrow, versioned JSON transport from returned HTML."""
import json
import re
from html.parser import HTMLParser


class ResultError(ValueError):
    """Stable transport/schema error; never includes page content."""


def _marker(marker):
    if not isinstance(marker, str) or not re.fullmatch(r'sa-extract-[a-f0-9]{32}', marker):
        raise ResultError('MARKER_ID')


def validate_result(value):
    if (not isinstance(value, dict) or type(value.get('version')) is not int
            or value['version'] != 1 or type(value.get('ok')) is not bool):
        raise ResultError('SCHEMA_INVALID')
    if value['ok']:
        if not isinstance(value.get('data'), dict):
            raise ResultError('SCHEMA_INVALID')
    elif (not isinstance(value.get('error'), dict)
          or not isinstance(value['error'].get('code'), str)
          or not re.fullmatch(r'[A-Z_]{1,64}', value['error']['code'])):
        raise ResultError('SCHEMA_INVALID')
    return value


def _decode(payload):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate key')
            result[key] = value
        return result
    def constant(_value):
        raise ValueError('nonfinite number')
    try:
        value = json.loads(payload, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, TypeError):
        raise ResultError('JSON_INVALID') from None
    return validate_result(value)


class _CarrierParser(HTMLParser):
    def __init__(self, marker):
        super().__init__(convert_charrefs=False)
        self.marker, self.matches, self.payloads = marker, 0, []
        self.active = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get('id') == self.marker:
            self.matches += 1
            if tag != 'script' or attributes.get('type') != 'application/json':
                raise ResultError('MARKER_FORMAT')
            if len(attributes) != len(attrs):
                raise ResultError('MARKER_FORMAT')
            self.active = []

    def handle_data(self, data):
        if self.active is not None:
            self.active.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.active is not None:
            self.payloads.append(''.join(self.active))
            self.active = None


def parse_html(html, marker):
    """Preferred parser: attribute ordering and quote normalization are tolerated."""
    _marker(marker)
    parser = _CarrierParser(marker)
    parser.feed(html)
    parser.close()
    if parser.matches != 1:
        raise ResultError('MARKER_COUNT')
    if len(parser.payloads) != 1:
        raise ResultError('MARKER_FORMAT')
    return _decode(parser.payloads[0])


def parse_marker(html, marker):
    """Exact framing protocol, not a general HTML extraction regex."""
    _marker(marker)
    if len(re.findall(r'\bid=[\"\']' + re.escape(marker) + r'[\"\']', html)) != 1:
        raise ResultError('MARKER_COUNT')
    matches = re.findall(r'<script id="' + re.escape(marker)
                         + r'" type="application/json">([^<]*)</script>', html)
    if len(matches) != 1:
        raise ResultError('MARKER_FORMAT')
    result = _decode(matches[0])
    if parse_html(html, marker) != result:
        raise ResultError('PARSER_MISMATCH')
    return result
