"""Explicit live stages. Default run.sh is offline; secrets are read from env only."""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import httpx
import httpx2
from mcp import ClientSession
from mcp.shared.exceptions import MCPError
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parent
MODEL = 'gpt-4.1-mini-2025-04-14'
CASES = ('complete', 'changed-layout', 'missing-price', 'conflicting-value', 'untrusted-instruction')
MAX_OUTPUT = 2000
MAX_INPUT_BYTES = 24000
# Standard token prices checked 2026-09-30 at the official model page.
INPUT_USD_PER_M = 0.40
OUTPUT_USD_PER_M = 1.60
# Reserve the full documented model context (including message framing),
# plus the output cap. This intentionally far exceeds the small fixture inputs.
RESERVED_INPUT_TOKENS = 1_047_576
RESERVATION = (RESERVED_INPUT_TOKENS * INPUT_USD_PER_M + MAX_OUTPUT * OUTPUT_USD_PER_M) / 1_000_000


def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def unpack(envelope):
    if envelope.get('isError'):
        raise ValueError('tool_error')
    structured = envelope.get('structuredContent')
    if isinstance(structured, dict) and isinstance(structured.get('result'), str):
        text = structured['result']
    else:
        blocks = [b.get('text', '') for b in envelope.get('content', []) if b.get('type') == 'text']
        text = '\n'.join(blocks)
        try:
            value = json.loads(text)
            if isinstance(value, dict) and isinstance(value.get('result'), str):
                text = value['result']
        except json.JSONDecodeError:
            pass
    if not text.strip():
        raise ValueError('empty_result')
    if text.lstrip().lower().startswith(('error', 'failed', 'unauthorized', 'forbidden')):
        raise ValueError('error_looking_text')
    return text


async def retrieve(out, fixture_commit):
    if len(fixture_commit) != 40 or any(c not in '0123456789abcdef' for c in fixture_commit):
        raise ValueError('full fixture commit required')
    urls = {case: f'https://raw.githubusercontent.com/ScrapingAnt/scrapingant-examples/{fixture_commit}/fixtures/mcp-catalog/{case}.html' for case in CASES}
    key = os.environ['SCRAPINGANT_API_KEY']
    async with httpx2.AsyncClient(headers={'x-api-key': key}, timeout=90, follow_redirects=False) as client:
        async with streamable_http_client('https://api.scrapingant.com/mcp/', http_client=client) as streams:
            async with ClientSession(*streams, read_timeout_seconds=90) as session:
                init = await session.initialize()
                listed = await session.list_tools()
                save(out/'discovery.json', {'initialization':init.model_dump(mode='json',by_alias=True), 'tools':listed.model_dump(mode='json',by_alias=True)})
                manifest = {'tested_at':datetime.now(timezone.utc).isoformat(), 'fixture_commit':fixture_commit,'python':platform.python_version(),'platform':platform.platform(),'retrievals':[]}
                for case, url in urls.items():
                    row={'case':case,'url':url,'arguments':{'url':url,'browser':False,'proxy_type':'datacenter'},'status':'attempted'}
                    manifest['retrievals'].append(row)
                    save(out/'retrievals.json',manifest)
                    try:
                        result = await session.call_tool('get_web_page_markdown',row['arguments'],read_timeout_seconds=90)
                        envelope=result.model_dump(mode='json',by_alias=True)
                        # Never retain an accidental credential echo in provider text.
                        encoded=json.dumps(envelope,ensure_ascii=False).replace(key,'[REDACTED]')
                        envelope=json.loads(encoded)
                        save(out/f'{case}.tool.json',envelope)
                        text=unpack(envelope)
                        (out/f'{case}.md').write_text(text)
                        row.update(status='ok',content_sha256=sha(text))
                    except ValueError as exc:
                        row.update(status='tool_or_content_error',error_code=str(exc))
                    except MCPError as exc:
                        row.update(status='protocol_error',error_type=type(exc).__name__)
                    except (httpx2.TransportError, TimeoutError) as exc:
                        row.update(status='transport_error',error_type=type(exc).__name__)
                    except Exception as exc:
                        row.update(status='session_or_unclassified_error',error_type=type(exc).__name__)
                    save(out/'retrievals.json',manifest)
                    print(case,row['status'],flush=True)


def extract(out):
    manifest=json.loads((out/'retrievals.json').read_text())
    prompt=(ROOT/'prompt.txt').read_text()
    schema=json.loads((ROOT/'schema.json').read_text())
    system=prompt+'\nApplication JSON Schema:\n'+json.dumps(schema)
    key=os.environ['OPENAI_API_KEY']
    budget=float(os.environ.get('MODEL_BUDGET_USD','0'))
    if not 0 < budget <= 10:
        raise ValueError('MODEL_BUDGET_USD must be >0 and <=10')
    ledger=out/'model-runs.json'
    if ledger.exists():
        raise ValueError('model-runs.json already exists; refusing accidental repeat spend')
    runs={'model':MODEL,'temperature':0,'max_completion_tokens':MAX_OUTPUT,'repetitions':3,'prompt_sha256':sha(system),'budget_usd':budget,'reservation_usd_per_attempt':RESERVATION,'pricing_source':'https://developers.openai.com/api/docs/models/gpt-4.1-mini','pricing_checked_at':'2026-09-30','runs':[]}
    save(ledger,runs)
    with httpx.Client(timeout=90,follow_redirects=False) as client:
        for retrieval in manifest['retrievals']:
            if retrieval['status'] != 'ok':
                continue
            case=retrieval['case'];markdown=(out/f'{case}.md').read_text()
            if sha(markdown)!=retrieval['content_sha256']:
                raise ValueError('retrieved content hash mismatch')
            user=json.dumps({'source_url':retrieval['url'],'untrusted_page_text':markdown},ensure_ascii=False)
            if len((system+user).encode()) > MAX_INPUT_BYTES:
                raise ValueError('input byte budget exceeded')
            for repeat in range(1,4):
                if (len(runs['runs'])+1)*RESERVATION > budget:
                    raise ValueError('budget exhausted before next attempt')
                name=f'{case}-{repeat}'
                row={'case':case,'repeat':repeat,'status':'attempted','reserved_usd':RESERVATION}
                runs['runs'].append(row);save(ledger,runs)
                try:
                    response=client.post('https://api.openai.com/v1/chat/completions',headers={'Authorization':'Bearer '+key},json={'model':MODEL,'temperature':0,'max_completion_tokens':MAX_OUTPUT,'response_format':{'type':'json_object'},'messages':[{'role':'system','content':system},{'role':'user','content':user}]})
                    row['http_status']=response.status_code
                    if response.status_code != 200:
                        row['status']='api_error'
                        # Do not print raw error messages, which can echo credentials.
                        body=response.json(); row['error_type']=body.get('error',{}).get('type'); row['error_code']=body.get('error',{}).get('code')
                    else:
                        data=response.json()
                        save(out/f'{name}.model.json',json.loads(json.dumps(data).replace(key,'[REDACTED]')))
                        row.update(status='ok',id=data['id'],usage=data['usage'],finish_reason=data['choices'][0]['finish_reason'])
                        usage=data['usage'];row['list_price_upper_estimate_usd']=(usage['prompt_tokens']*INPUT_USD_PER_M+usage['completion_tokens']*OUTPUT_USD_PER_M)/1_000_000
                except Exception as exc:
                    row.update(status='transport_or_response_error',error_type=type(exc).__name__)
                save(ledger,runs)
                print(name,row['status'],flush=True)
                if row['status'] != 'ok':
                    raise RuntimeError('model attempt failed; stopping without retries')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['retrieve','extract']);parser.add_argument('--output',required=True,type=Path);parser.add_argument('--fixture-commit');parser.add_argument('--retrieval-capture',type=Path)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    if args.stage=='retrieve':
        if (args.output/'retrievals.json').exists():raise ValueError('retrieval capture exists; use a new output directory')
        asyncio.run(retrieve(args.output,args.fixture_commit or ''))
    else:
        if args.retrieval_capture:
            import shutil
            if (args.output/'retrievals.json').exists():raise ValueError('output already has retrievals')
            for pattern in ('retrievals.json','discovery.json','*.md','*.tool.json'):
                for source in args.retrieval_capture.glob(pattern):
                    shutil.copy2(source,args.output/source.name)
        extract(args.output)

if __name__=='__main__':main()
