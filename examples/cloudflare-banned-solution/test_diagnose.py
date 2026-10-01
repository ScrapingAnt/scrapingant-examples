import unittest
from diagnose import inspect_response


class ResponseGateTests(unittest.TestCase):
    def response(self, status=200, content_type='application/json', body='{"records":[{"id":"A1","name":"Widget","price":"12.50"}]}'):
        return {'status':status,'headers':{'content-type':content_type,'cf-ray':'synthetic-ray'},'body':body}

    def test_valid_json_records_are_accepted(self):
        result=inspect_response(self.response())
        self.assertEqual(result['action'],'accept')
        self.assertEqual(result['records'][0]['id'],'A1')

    def test_denial_status_never_becomes_records(self):
        result=inspect_response(self.response(403))
        self.assertEqual(result['action'],'stop')
        self.assertEqual(result['reason'],'http_failure')
        self.assertNotIn('records',result)

    def test_1005_html_is_rejected_even_with_200(self):
        result=inspect_response(self.response(content_type='text/html',body='<h1>Error 1005</h1><p>Access denied</p>'))
        self.assertEqual(result['action'],'stop')
        self.assertEqual(result['reason'],'possible_1005_page')
        self.assertEqual(result['ray_id'],'synthetic-ray')

    def test_other_html_is_not_json_success(self):
        self.assertEqual(inspect_response(self.response(content_type='text/html',body='<h1>Challenge</h1>'))['reason'],'unexpected_content_type')

    def test_invalid_json_is_stopped(self):
        self.assertEqual(inspect_response(self.response(body='{'))['reason'],'invalid_json')

    def test_error_envelope_is_not_records(self):
        self.assertEqual(inspect_response(self.response(body='{"error":"denied"}'))['reason'],'invalid_records')

    def test_empty_records_are_stopped(self):
        self.assertEqual(inspect_response(self.response(body='{"records":[]}'))['reason'],'invalid_records')

    def test_duplicate_ids_are_stopped(self):
        self.assertEqual(inspect_response(self.response(body='{"records":[{"id":"A1","name":"a","price":"1"},{"id":"A1","name":"b","price":"2"}]}'))['reason'],'invalid_records')

    def test_invalid_prices_are_stopped(self):
        for price in ['NaN','Infinity','-1','garbage']:
            with self.subTest(price=price):
                body='{"records":[{"id":"A1","name":"a","price":"'+price+'"}]}'
                self.assertEqual(inspect_response(self.response(body=body))['reason'],'invalid_records')

    def test_json_business_text_is_not_a_denial_detector(self):
        body='{"records":[{"id":"A1","name":"Error 1005 Access Denied handbook","price":"1"}]}'
        self.assertEqual(inspect_response(self.response(body=body))['action'],'accept')

    def test_extra_record_fields_are_stopped(self):
        body='{"records":[{"id":"A1","name":"a","price":"1","unexpected":true}]}'
        self.assertEqual(inspect_response(self.response(body=body))['reason'],'invalid_records')

    def test_missing_and_non_string_fields_are_stopped(self):
        for body in ['{"records":[{"id":"A1","price":"1"}]}','{"records":[{"id":true,"name":"a","price":"1"}]}','{"records":[{"id":"A1","name":" ","price":"1"}]}']:
            with self.subTest(body=body):self.assertEqual(inspect_response(self.response(body=body))['reason'],'invalid_records')

if __name__=='__main__':unittest.main()
