"""Named synthetic diagnostics only; fake transports never call a provider."""
import copy, io, json, unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch
import recover_contact as r

SPEC, VALIDATORS, CRYPTO, RECIPIENT = r.load_reviewed()

def native():
    return {'id':'R'*17,'userId':'U'*17,'actId':SPEC['actor_id'],
        'defaultDatasetId':'D'*17,'defaultKeyValueStoreId':'K'*17,'defaultRequestQueueId':'Q'*17,
        'buildNumber':SPEC['build'],'options':{**SPEC['options'],'maxTotalChargeUsd':0.5},
        'status':'SUCCEEDED','startedAt':'2026-10-06T13:30:08.600Z',
        'finishedAt':'2026-10-06T13:30:12.600Z','usageTotalUsd':0.2}

def synthetic_spec():
    spec = copy.deepcopy(SPEC); spec['owner_id_sha256'] = r.sha(('U'*17).encode())
    return spec

def listing(rows=None, total=None):
    rows = [native()] if rows is None else rows
    return {'data':{'offset':0,'limit':5,'count':len(rows),
        'total':len(rows) if total is None else total,'desc':False,'items':rows}}

def metadata():
    n = native()
    return {'data':{'id':n['defaultKeyValueStoreId'],'userId':n['userId'],
        'actId':n['actId'],'actRunId':n['id'],'name':None,
        'createdAt':n['startedAt'],'modifiedAt':n['finishedAt'],
        'stats':{'storageBytes':1000}}}

def replies():
    return [listing(),{'data':native()},metadata(),SPEC['native_input'],{'data':native()}]

class Response:
    def __init__(self, raw, *, status=200, clock=None, tick=0):
        self.raw = io.BytesIO(raw); self.status = status; self.closed = False
        self.clock = clock; self.tick = tick
    def getheader(self, key):
        return 'application/json' if key == 'Content-Type' else None
    def read1(self, length):
        if self.clock: self.clock[0] += self.tick
        return self.raw.read(length)
    def close(self): self.closed = True

def capture(values=None):
    values = replies() if values is None else values
    blobs = [json.dumps(x,separators=(',',':')).encode() for x in values]
    calls = []; files = {}
    def opener(request, timeout):
        calls.append(request)
        return Response(blobs[len(calls)-1])
    with patch.object(r,'RECOVERY_READY',True):
        transport = r.Transport('named_synthetic_token_123',synthetic_spec(),opener=opener)
        result = r.collect(transport,synthetic_spec(),VALIDATORS,
            lambda stage,raw:files.setdefault(stage,r.sha(raw)),
            utc=lambda:'2026-10-06T14:00:00Z')
    return result, calls, files

class RecoveryTests(unittest.TestCase):
    def test_closed_guard_blocks_before_opener(self):
        with self.assertRaises(r.Stop) as raised:
            r.Transport('named_synthetic_token_123',SPEC,opener=lambda *a: self.fail())
        self.assertEqual(raised.exception.category,'guard_closed')

    def test_exact_five_GETs_and_latest_meter_once(self):
        result, calls, files = capture()
        self.assertTrue(result['terminal_identity_and_input_verified'])
        self.assertTrue(result['capture_complete'])
        self.assertEqual(result['latest_terminal_run_meter']['usage_total_usd'],'0.2')
        self.assertTrue(result['latest_meter_snapshot_used_once'])
        self.assertEqual([x.get_method() for x in calls],['GET']*5)
        paths = [urlsplit(x.full_url).path for x in calls]
        self.assertEqual(paths,['/v2/actors/'+SPEC['actor_id']+'/runs','/v2/actor-runs/'+'R'*17,
            '/v2/key-value-stores/'+'K'*17,'/v2/key-value-stores/'+'K'*17+'/records/INPUT',
            '/v2/actor-runs/'+'R'*17])
        self.assertEqual(set(files),set(r.STAGES))
        self.assertFalse(result['ready_for_next_Actor_start'])
        self.assertEqual(result['hold_release_usd'],'0')
        self.assertFalse(result['rejected_before_run_proven'])

    def test_first_list_filters_fixed_time_and_no_token_URL(self):
        _, calls, _ = capture()
        query = parse_qs(urlsplit(calls[0].full_url).query)
        self.assertEqual(query,{'limit':['5'],'offset':['0'],'desc':['false'],
            'startedAfter':[SPEC['started_after']],'startedBefore':[SPEC['started_before']]})
        self.assertTrue(all('named_synthetic_token' not in x.full_url for x in calls))
        self.assertTrue(all(x.get_header('Authorization') == 'Bearer named_synthetic_token_123' for x in calls))

    def test_empty_complete_list_remains_absence_only(self):
        result, calls, _ = capture([listing([])])
        self.assertTrue(result['complete_empty_window_observed'])
        self.assertTrue(result['capture_complete'])
        self.assertEqual(len(calls),1)
        self.assertIsNone(result['latest_terminal_run_meter'])
        self.assertFalse(result['rejected_before_run_proven'])
        self.assertFalse(result['ready_for_next_Actor_start'])

    def test_truncated_page_does_not_select_or_paginate(self):
        result,calls,_ = capture([listing(total=6)])
        self.assertEqual(result['diagnostic']['category'],'incomplete_list')
        self.assertEqual(len(calls),1)

    def test_multiple_candidates_stop_before_details(self):
        other = native(); other['id'] = 'S'*17
        result,calls,_ = capture([listing([native(),other])])
        self.assertEqual(result['diagnostic']['category'],'multiple_candidates')
        self.assertEqual(len(calls),1)

    def test_duplicate_ids_and_boolean_counters_rejected(self):
        for value in (listing([native(),native()]),listing()):
            if len(value['data']['items']) == 1: value['data']['count'] = True
            result,calls,_ = capture([value])
            self.assertFalse(result['capture_complete']); self.assertEqual(len(calls),1)

    def test_wrong_owner_or_time_or_actor_in_list_stops(self):
        for key,value in (('userId','X'*17),('actId','X'*17),('startedAt','2026-10-06T13:29:59Z')):
            row = native(); row[key] = value
            result,calls,_ = capture([listing([row])])
            self.assertEqual(result['diagnostic']['category'],'scope_mismatch')
            self.assertEqual(len(calls),1)

    def test_detail_wrong_owner_build_options_stop_before_input(self):
        for mutate in (lambda n:n.update(userId='X'*17),lambda n:n.update(buildNumber='0.2.239'),
                       lambda n:n['options'].update(maxTotalChargeUsd=0.6),
                       lambda n:n['options'].update(memoryMbytes=True)):
            values = replies(); mutate(values[1]['data'])
            result,calls,_ = capture(values)
            self.assertFalse(result['capture_complete']); self.assertEqual(len(calls),2)

    def test_active_candidate_stops_without_abort(self):
        values = replies(); values[1]['data'].update(status='RUNNING',finishedAt=None)
        result,calls,_ = capture(values)
        self.assertEqual(result['diagnostic']['category'],'nonterminal')
        self.assertEqual(len(calls),2); self.assertEqual(result['aborts'],0)

    def test_foreign_or_named_or_stale_KV_stops_before_INPUT(self):
        for key,value in (('actRunId','X'*17),('userId','X'*17),('name','prior-state'),
            ('createdAt','2026-10-06T13:29:59Z')):
            values = replies(); values[2]['data'][key] = value
            result,calls,_ = capture(values)
            self.assertFalse(result['capture_complete']); self.assertEqual(len(calls),3)

    def test_INPUT_mismatch_never_reads_meter(self):
        values = replies(); values[3] = {**values[3],'maxRequests':7}
        result,calls,_ = capture(values)
        self.assertEqual(result['diagnostic']['category'],'input_mismatch')
        self.assertEqual(len(calls),4)
        self.assertIsNone(result['latest_terminal_run_meter'])

    def test_meter_missing_null_boolean_and_overcap_stop(self):
        for amount in (None,True,0.51):
            values = replies(); values[-1]['data']['usageTotalUsd'] = amount
            result,calls,_ = capture(values)
            self.assertFalse(result['capture_complete']); self.assertEqual(len(calls),5)

    def test_final_meter_changed_identity_or_status_rejected(self):
        for key,value in (('id','X'*17),('status','FAILED'),('finishedAt','2026-10-06T13:30:13Z')):
            values = replies(); values[-1]['data'][key] = value
            result,_,_ = capture(values)
            self.assertFalse(result['terminal_identity_and_input_verified'])

    def test_HTTP_error_not_read_or_retried(self):
        class PrivateBody(io.BytesIO):
            def read(self,*args): raise AssertionError('raw error must not be read')
        private = PrivateBody(b'private provider error body')
        def opener(*args,**kwargs): raise HTTPError('https://api.apify.com',400,'private',{},private)
        with patch.object(r,'RECOVERY_READY',True):
            t = r.Transport('named_synthetic_token_123',synthetic_spec(),opener=opener)
            result = r.collect(t,synthetic_spec(),VALIDATORS,lambda *a:self.fail())
            self.assertEqual(result['diagnostic'],{'category':'http_error','stage':'list','http_status':400})
            self.assertEqual(t.calls,1); self.assertTrue(private.closed)
            with self.assertRaises(r.Stop): t.get('list')

    def test_response_limit_and_trickle_deadline(self):
        for raw,tick in ((b'x'*131073,0),(b'x'*16384,8)):
            clock = [0.0]
            response = Response(raw,clock=clock,tick=tick)
            with patch.object(r,'RECOVERY_READY',True):
                t = r.Transport('named_synthetic_token_123',synthetic_spec(),
                    opener=lambda *a,**k:response,clock=lambda:clock[0])
                with self.assertRaises(r.Stop) as raised: t.get('list')
                self.assertIn(raised.exception.category,('body_limit','deadline_exceeded'))
                self.assertTrue(response.closed); self.assertTrue(t.failed)

    def test_no_alternate_route_and_no_rebind(self):
        with patch.object(r,'RECOVERY_READY',True):
            t = r.Transport('named_synthetic_token_123',synthetic_spec(),opener=lambda *a:self.fail())
            for stage in ('run','abort','start','export','delete','meter'):
                with self.assertRaises(r.Stop): t.route(stage)
            t.calls = 1; t.bind_candidate('R'*17)
            with self.assertRaises(r.Stop): t.bind_candidate('S'*17)

    def test_duplicate_JSON_nonfinite_and_currency_strings_rejected(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1e1000}'):
            with self.assertRaises(r.Stop): r.strict(raw)
        values = replies(); values[-1]['data']['usageTotalUsd'] = '0.20'
        result,_,_ = capture(values)
        self.assertFalse(result['capture_complete'])

    def test_public_projection_excludes_identity_and_meter(self):
        result,_,_ = capture()
        public = r.public_projection(result,{'plaintext_sha256':'a'*64,'ciphertext_sha256':'b'*64})
        text = r.canonical(public).decode()
        self.assertNotIn('R'*17,text); self.assertNotIn('U'*17,text)
        self.assertNotIn('latest_terminal_run_meter',public)
        self.assertNotIn('files',public)

    def test_execute_output_rejection_before_token_access(self):
        with patch.object(r,'RECOVERY_READY',True), patch.object(Path,'exists',return_value=True):
            with self.assertRaises(r.Stop) as raised:
                r.execute({'APIFY_CONTACT_READONLY_OPT_IN':'yes'})
            self.assertEqual(raised.exception.category,'preflight_failed')

if __name__ == '__main__': unittest.main()
