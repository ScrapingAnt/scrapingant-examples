"""Offline protocol regression tests: no requests, credentials or provider credits."""
import importlib.util
import builtins
import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name('02_tool_call.py')
def load_definitions():
    spec = importlib.util.spec_from_file_location('mcp_tool_call', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module) # No key read, dependency import or HTTP at import.
    return vars(module)

class Response:
    def __init__(self, text='', status=200, mime='application/json', headers=None):
        self.text, self.status_code = text, status
        self.headers = {'content-type': mime, **(headers or {})}
    def json(self):
        return json.loads(self.text)

def rpc(result=None, request_id=2, **extra):
    return {'jsonrpc': '2.0', 'id': request_id, 'result': result if result is not None else {'content': [{'type':'text','text':'owned fixture'}]}, **extra}

def stream(*messages):
    return Response(''.join('data: '+json.dumps(m)+'\n\n' for m in messages), mime='text/event-stream')

class ProtocolTests(unittest.TestCase):
    def setUp(self): self.ns = load_definitions()
    def parse(self, response, request_id=2):
        return self.ns['parse_response'](response, request_id)
    def assert_rejected(self, response):
        with self.assertRaises(ValueError) as raised: self.parse(response)
        self.assertNotIn('SECRET', str(raised.exception))
    def test_notification_before_response(self):
        m=self.parse(stream({'jsonrpc':'2.0','method':'notifications/progress','params':{}},rpc()))
        self.assertEqual(m.get('id'),2)
    def test_unrelated_response_before_matching_response(self):
        self.assertEqual(self.parse(stream(rpc(request_id=99),rpc()))['id'],2)
    def test_valid_json(self): self.assertEqual(self.parse(Response(json.dumps(rpc())))['id'],2)
    def test_multiline_sse_and_comments(self):
        r=Response(': heartbeat\r\nevent: message\r\ndata: {"jsonrpc":"2.0",\r\ndata: "id":2,"result":{"content":[]}}\r\n\r\n',mime='text/event-stream; charset=utf-8')
        self.assertEqual(self.parse(r)['id'],2)
    def test_sse_unicode_text_is_not_an_event_boundary(self):
        value=rpc({'content':[{'type':'text','text':'first\u2028middle\u0085last'}]})
        response=Response('data: '+json.dumps(value,ensure_ascii=False)+'\n\n',mime='text/event-stream')
        try: actual=self.parse(response)
        except ValueError:self.fail('Valid Unicode JSON text was split as an SSE event')
        self.assertEqual(actual,value)
    def test_import_does_not_read_key_or_load_http_dependency(self):
        original_import=builtins.__import__
        def guarded(name,*args,**kwargs):
            if name=='requests':raise AssertionError('HTTP dependency loaded at import')
            return original_import(name,*args,**kwargs)
        with patch('os.environ.get',side_effect=AssertionError('Environment read at import')),patch('builtins.__import__',side_effect=guarded):
            self.assertTrue(callable(load_definitions()['main']))
    def test_sse_final_event_without_blank_line(self):
        self.assertEqual(self.parse(Response('data:'+json.dumps(rpc()),mime='text/event-stream'))['id'],2)
    def test_jsonrpc_error_is_safe(self):
        self.assert_rejected(Response(json.dumps({'jsonrpc':'2.0','id':2,'error':{'code':-32600,'message':'SECRET','data':'SECRET'}})))
    def test_non200_and_nonjson_are_safe(self):
        for r in [Response('SECRET',status=403),Response('SECRET',mime='text/html'),Response('SECRET'),Response('SECRET',status=202)]:
            with self.subTest(status=r.status_code,mime=r.headers): self.assert_rejected(r)
    def test_malformed_envelopes(self):
        for value in [[],{}, {'jsonrpc':'2.0','id':2},rpc(result='SECRET'),rpc(error={'code':1}),rpc(request_id='2'),rpc(request_id=True),{'jsonrpc':'1.0','id':2,'result':{}}, {'jsonrpc':'2.0','result':{}}]:
            with self.subTest(value=value):self.assert_rejected(Response(json.dumps(value)))
    def test_missing_correlated_sse_response(self):
        self.assert_rejected(stream({'jsonrpc':'2.0','method':'notifications/progress'}))
    def test_content_validation_and_tool_error(self):
        self.assertTrue(callable(self.ns.get('validate_tool_result')), 'tool results need explicit validation')
        fn=self.ns['validate_tool_result']
        self.assertEqual(fn(rpc()['result']),1)
        for result in [{}, {'content':'SECRET'}, {'content':[{}]}, {'content':[{'type':'text','text':1}]}, {'isError':True,'content':[{'type':'text','text':'SECRET'}]}, {'isError':'false','content':[]}]:
            with self.subTest(result=result),self.assertRaises(ValueError) as raised:fn(result)
            self.assertNotIn('SECRET',str(raised.exception))
    def test_main_headers_ids_and_fail_fast(self):
        self.assertTrue(callable(self.ns.get('main')), 'main must be import-safe and testable offline')
        records=[]
        class Session:
            def post(inner,url,**kwargs):
                records.append(kwargs)
                msg=kwargs['json'];request_id=msg.get('id')
                if msg['method']=='initialize':return Response(json.dumps(rpc({'protocolVersion':'2025-06-18'},request_id=1)),headers={'Mcp-Session-Id':'SECRET-SESSION'})
                if msg['method']=='notifications/initialized':return Response('',status=202)
                return Response(json.dumps(rpc(request_id=request_id)))
        output=io.StringIO()
        with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):code=self.ns['main'](Session(),'SECRET-KEY')
        self.assertEqual(code,0);self.assertEqual(len(records),4)
        self.assertEqual([r['json'].get('id') for r in records],[1,None,2,3])
        for r in records[1:]:
            self.assertEqual(r['headers']['MCP-Protocol-Version'],'2025-06-18')
            self.assertEqual(r['headers']['Mcp-Session-Id'],'SECRET-SESSION')
        self.assertNotIn('SECRET',output.getvalue())
    def test_main_failure_is_nonzero_no_retry(self):
        self.assertTrue(callable(self.ns.get('main')), 'main needs a bounded failure exit')
        class Session:
            calls=0
            def post(inner,url,**kwargs):
                inner.calls+=1
                return Response('SECRET',status=403)
        session=Session();out=io.StringIO()
        with contextlib.redirect_stderr(out):code=self.ns['main'](session,'SECRET-KEY')
        self.assertEqual(code,1);self.assertEqual(session.calls,1);self.assertNotIn('SECRET',out.getvalue())
    def test_main_tool_failures_do_not_call_second_browser(self):
        failures = [Response('SECRET', status=403),
                    Response(json.dumps({'jsonrpc':'2.0','id':2,'error':{'code':-32600,'message':'SECRET'}})),
                    Response(json.dumps(rpc({'isError':True,'content':[{'type':'text','text':'SECRET'}]}))),
                    Response(json.dumps(rpc({'content':'SECRET'})))]
        for failure in failures:
            class Session:
                calls=0
                def post(inner,url,**kwargs):
                    inner.calls+=1
                    if inner.calls==1:return Response(json.dumps(rpc({'protocolVersion':'2025-06-18'},request_id=1)))
                    if inner.calls==2:return Response('',status=202)
                    return failure
            session=Session();out=io.StringIO()
            with self.subTest(response=failure.status_code),contextlib.redirect_stderr(out):
                self.assertEqual(self.ns['main'](session,'SECRET-KEY'),1)
            self.assertEqual(session.calls,3)
            self.assertNotIn('SECRET',out.getvalue())
    def test_main_rejects_bad_negotiation_and_notification(self):
        cases=[({'protocolVersion':'other'}, {},202),
               ({'protocolVersion':'2025-06-18'}, {'Mcp-Session-Id':'SECRET SESSION'},202),
               ({'protocolVersion':'2025-06-18'}, {},400)]
        for result,headers,status in cases:
            class Session:
                calls=0
                def post(inner,url,**kwargs):
                    inner.calls+=1
                    return Response(json.dumps(rpc(result,request_id=1)),headers=headers) if inner.calls==1 else Response('SECRET',status=status)
            session=Session();out=io.StringIO()
            with self.subTest(result=result,headers=headers,status=status),contextlib.redirect_stderr(out):
                self.assertEqual(self.ns['main'](session,'SECRET-KEY'),1)
            self.assertLessEqual(session.calls,2)
            self.assertNotIn('SECRET',out.getvalue())
    def test_transport_exception_body_is_not_logged(self):
        class Session:
            def post(inner,*args,**kwargs):raise RuntimeError('SECRET response/header')
        out=io.StringIO()
        with contextlib.redirect_stderr(out):self.assertEqual(self.ns['main'](Session(),'SECRET-KEY'),1)
        self.assertNotIn('SECRET',out.getvalue())
    def test_missing_key_no_requests(self):
        self.assertTrue(callable(self.ns.get('main')), 'missing key needs safe failure')
        with contextlib.redirect_stderr(io.StringIO()):self.assertEqual(self.ns['main'](object(),''),1)

if __name__=='__main__':unittest.main()
