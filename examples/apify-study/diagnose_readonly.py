"""Exactly the existing two read-only account routes; encrypted projection only.

No run, storage, token-list, security change or financial account operation.
Only a private username fingerprint can associate the existing Console session
with the injected account; profile values themselves are never retained.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

import evidence_transport as crypto
import runner
from workflow_driver import private_paths

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'apify-calibration'))
import account_capabilities as account


def projection(user,limits):
    snapshot=account.project(user,limits)
    data=account.object_field(user,'data')
    username=data.get('username')
    username=(username.lower() if isinstance(username,str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',username) else None)
    source=account.object_field(limits,'data')
    maximum=account.number(account.object_field(source,'limits').get('maxMonthlyUsageUsd'))
    current=account.number(account.object_field(source,'current').get('monthlyUsageUsd'))
    headroom=account.difference(maximum,current)
    return {'schema_version':1,'evidence_type':'private_readonly_access_diagnosis',
        'username_fingerprint_sha256':hashlib.sha256(username.encode()).hexdigest() if username else None,
        'is_organization':account.boolean(data.get('isOrganization')),
        'account_projection':snapshot,
        'monthly_ceiling_has_0_14_usd_headroom':None if headroom is None else headroom>=account.Decimal('0.14'),
        'monthly_ceiling_schema_complete':maximum is not None and current is not None,
        'approval_state':'not_available_in_documented_api_projection',
        'run_permission_verified':False,'provider_start_attempts':0,'deletions':0}


def execute():
    account.require_guard() # Closed before environment/token access unless explicitly reviewed.
    folder,binary=private_paths(os.environ)
    recipient=(ROOT/'recipient.txt').read_text().strip()
    preflight=folder/'diagnosis-preflight.age'
    crypto.encrypt_capture(b'{"synthetic_transport_preflight":true,"provider_calls":0}',preflight,binary,recipient)
    preflight.unlink()
    token=os.environ.get('APIFY_TOKEN')
    account.validate_token(token)
    transport=account.AccountTransport(token)
    values=[];reads=[]
    for stage,url in zip(('identity','limits'),account.URLS):
        try:
            values.append(transport.get(url));reads.append({'stage':stage,'http_status':200,'category':'ok'})
        except Exception as exc:
            safe=exc if isinstance(exc,account.ProbeError) else account.ProbeError('transport_error')
            reads.append({'stage':stage,'http_status':safe.status,'category':safe.category});break
    evidence=projection(*values) if len(values)==2 else projection(None,None)
    evidence['reads']=reads;evidence['requests_attempted']=len(reads)
    receipt=crypto.encrypt_capture(runner.canonical(evidence),ROOT/'diagnosis.age',binary,recipient)
    public={'evidence_type':'encrypted_readonly_access_diagnosis','requests_attempted':len(reads),
            'reads':reads,'provider_start_attempts':0,'deletions':0,
            'plaintext_sha256':receipt['plaintext_sha256'],'ciphertext_sha256':receipt['ciphertext_sha256']}
    crypto.durable_write(ROOT/'diagnosis-public.json',runner.canonical(public))
    return public


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    if not args.execute:
        print(json.dumps({'mode':'offline','provider_requests':0}));return 0
    try:print(json.dumps(execute(),sort_keys=True));return 0
    except Exception:
        print(json.dumps({'category':'read_only_diagnosis_blocked','owner_attention_required':True}));return 1


if __name__=='__main__':raise SystemExit(main())
