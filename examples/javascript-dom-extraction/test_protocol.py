import json
import unittest
from protocol import ResultError, parse_html, parse_marker, validate_result

MARKER = 'sa-extract-' + '1' * 32
PROBE = {'text': '</script><!--<script> & &amp; "quoted" \\ newline\nКиїв 中文 🕷\u2028\u2029'}
RESULT = {'version': 1, 'ok': True, 'data': PROBE}

def html_for(result=RESULT, marker=MARKER):
    payload = json.dumps(result, ensure_ascii=False).replace('<', '\\u003c')
    return '<html><body><script id="'+marker+'" type="application/json">'+payload+'</script></body></html>'

class ProtocolTests(unittest.TestCase):
    def test_raw_script_json_preserves_special_text_without_entity_decoding(self):
        html = html_for()
        self.assertEqual(parse_marker(html, MARKER), RESULT)
        self.assertEqual(parse_html(html, MARKER), RESULT)
        self.assertIn('&amp;', parse_marker(html, MARKER)['data']['text'])
    def test_missing_marker_is_error_not_empty_result(self):
        for parse in [parse_marker, parse_html]:
            with self.assertRaisesRegex(ResultError, 'MARKER_COUNT'): parse('<html>no result</html>', MARKER)
    def test_duplicate_marker_is_rejected(self):
        for parse in [parse_marker, parse_html]:
            with self.assertRaisesRegex(ResultError, 'MARKER_COUNT'): parse(html_for()+html_for(), MARKER)
    def test_unescaped_closing_script_cannot_be_accepted(self):
        raw = html_for().replace('\\u003c', '<')
        for parse in [parse_marker, parse_html]:
            with self.assertRaises(ResultError): parse(raw, MARKER)
    def test_normalized_attribute_order_fails_strict_protocol_but_parser_handles_it(self):
        html=html_for().replace('id="'+MARKER+'" type="application/json"', 'type="application/json" id="'+MARKER+'"')
        with self.assertRaisesRegex(ResultError, 'MARKER_FORMAT'): parse_marker(html, MARKER)
        self.assertEqual(parse_html(html, MARKER), RESULT)
    def test_bad_json_duplicate_keys_and_nonfinite_values_are_rejected(self):
        for payload in ['{', '{"version":1,"version":1,"ok":true,"data":{}}', '{"version":1,"ok":true,"data":{"x":NaN}}']:
            html='<script id="'+MARKER+'" type="application/json">'+payload+'</script>'
            with self.assertRaisesRegex(ResultError, 'JSON_INVALID'): parse_marker(html, MARKER)
    def test_version_bool_status_string_or_wrong_shape_rejected(self):
        for result in [{'version':True,'ok':True,'data':{}},{'version':1,'ok':'true','data':{}},{'version':1,'ok':True,'data':[]},{'version':2,'ok':True,'data':{}}]:
            with self.assertRaisesRegex(ResultError,'SCHEMA_INVALID'): validate_result(result)
    def test_extraction_error_is_separate_from_transport(self):
        error={'version':1,'ok':False,'error':{'code':'ELEMENT_MISSING'}}
        self.assertEqual(parse_marker(html_for(error),MARKER),error)
    def test_marker_id_input_cannot_change_regex_or_html(self):
        for marker in ['x.*','bad" id="x','sa-extract-'+'a'*31]:
            with self.assertRaisesRegex(ResultError,'MARKER_ID'): parse_marker(html_for(),marker)
    def test_comment_carrier_and_unquoted_duplicate_are_rejected(self):
        for html in ['<!--'+html_for()+'-->', html_for()+'<script id='+MARKER+' type="application/json">{}</script>']:
            with self.assertRaisesRegex(ResultError, 'MARKER_COUNT'): parse_marker(html, MARKER)

if __name__=='__main__': unittest.main()
