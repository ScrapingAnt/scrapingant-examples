"""Call an MCP text tool; imports and regression tests never make HTTP requests.

Direct execution retains the two browser-off/on calls and requires an API key.
No retries or raw server response content are printed.
"""
import json
import os
import sys

ENDPOINT = 'https://api.scrapingant.com/mcp/'
FIXTURE = 'https://scrapingant.github.io/scrapingant-examples/fixtures/dynamic-delayed.html'


class MCPError(ValueError):
    """A fixed, safe diagnostic that contains no server body or credentials."""


def header(response, name):
    return next((v for k, v in response.headers.items() if k.lower() == name.lower()), '')


def sse_data(text):
    """Join data lines within each SSE event; ignore comments and event metadata."""
    data = []
    # SSE recognizes CR/LF only; Unicode separators may be valid JSON text.
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not line:
            if data:
                yield '\n'.join(data)
                data = []
        elif line.startswith('data:'):
            value = line[5:]
            data.append(value[1:] if value.startswith(' ') else value)
    if data:
        yield '\n'.join(data)


def parse_response(response, request_id):
    """Find the matching JSON-RPC response, including after SSE notifications."""
    if response.status_code != 200:
        # Status comes from the HTTP client; never include the untrusted body.
        raise MCPError(f'HTTP request failed (status {response.status_code})')
    mime = header(response, 'content-type').split(';', 1)[0].strip().lower()
    if mime == 'text/event-stream':
        payloads = sse_data(response.text)
    elif mime == 'application/json':
        payloads = [response.text]
    else:
        raise MCPError('Unsupported response content type')
    for payload in payloads:
        try:
            message = json.loads(payload)
        except (ValueError, TypeError):
            raise MCPError('Invalid JSON response') from None
        if not isinstance(message, dict) or message.get('jsonrpc') != '2.0':
            raise MCPError('Invalid JSON-RPC envelope')
        if 'id' not in message and isinstance(message.get('method'), str):
            continue # Server notification: not this request's response.
        if type(message.get('id')) is not type(request_id) or message.get('id') != request_id:
            continue
        if ('result' in message) == ('error' in message):
            raise MCPError('Response must contain exactly one result or error')
        if 'error' in message:
            code = message['error'].get('code') if isinstance(message['error'], dict) else None
            suffix = f' (code {code})' if type(code) is int else ''
            raise MCPError('JSON-RPC request failed' + suffix)
        if not isinstance(message['result'], dict):
            raise MCPError('Invalid JSON-RPC result')
        return message
    raise MCPError('No matching JSON-RPC response')


def validate_tool_result(result):
    """Validate this text tool's content without printing or trusting its text."""
    if not isinstance(result, dict) or not isinstance(result.get('content'), list):
        raise MCPError('Tool result is missing a content list')
    if 'isError' in result and type(result['isError']) is not bool:
        raise MCPError('Invalid tool error flag')
    if result.get('isError', False):
        raise MCPError('Tool execution failed (isError=true)')
    for block in result['content']:
        if not isinstance(block, dict) or block.get('type') != 'text' or not isinstance(block.get('text'), str):
            raise MCPError('Text tool returned invalid content')
    return len(result['content'])


def main(session=None, api_key=None):
    api_key = os.environ.get('SCRAPINGANT_API_KEY', '') if api_key is None else api_key
    if not api_key:
        print('MCP example failed: SCRAPINGANT_API_KEY is not set', file=sys.stderr)
        return 1
    try:
        if session is None:
            import requests
            session = requests.Session()
        headers = {'Content-Type': 'application/json',
                   'Accept': 'application/json, text/event-stream', 'x-api-key': api_key}
        response = session.post(ENDPOINT, headers=dict(headers), json={
            'jsonrpc':'2.0', 'id':1, 'method':'initialize', 'params':{
                'protocolVersion':'2025-06-18', 'capabilities':{},
                'clientInfo':{'name':'blog-example','version':'1.0'}}}, timeout=60)
        initialized = parse_response(response, 1)['result']
        if initialized.get('protocolVersion') != '2025-06-18':
            raise MCPError('Server selected an unsupported protocol version')
        headers['MCP-Protocol-Version'] = initialized['protocolVersion']
        session_id = header(response, 'Mcp-Session-Id')
        if session_id:
            if not isinstance(session_id, str) or any(not 0x21 <= ord(c) <= 0x7e for c in session_id):
                raise MCPError('Invalid negotiated session header')
            headers['Mcp-Session-Id'] = session_id
        notification = session.post(ENDPOINT, headers=dict(headers), json={
            'jsonrpc':'2.0','method':'notifications/initialized'}, timeout=60)
        if notification.status_code != 202:
            raise MCPError('Initialization notification was not accepted')
        for request_id, browser in enumerate((False, True), start=2):
            response = session.post(ENDPOINT, headers=dict(headers), json={
                'jsonrpc':'2.0','id':request_id,'method':'tools/call','params':{
                    'name':'get_web_page_text','arguments':{'url':FIXTURE,'browser':browser}}}, timeout=120)
            count = validate_tool_result(parse_response(response, request_id)['result'])
            print(f'get_web_page_text browser={browser}: received {count} text blocks')
        return 0
    except MCPError as error:
        print(f'MCP example failed: {error}', file=sys.stderr)
        return 1
    except Exception:
        # Transport exceptions can contain headers, URLs or server text.
        print('MCP example failed: transport or dependency error', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
