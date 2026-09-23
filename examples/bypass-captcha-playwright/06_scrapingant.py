"""Observe the returned CAPTCHA demo, without equating fetched HTML to a solve."""
import hashlib,json,os,re,time
from datetime import datetime,timezone
from pathlib import Path
import requests

URL='https://www.google.com/recaptcha/api2/demo'
def main():
    key=os.environ.get('SCRAPINGANT_API_KEY')
    if not key:
        print(json.dumps({'outcome':'unavailable','reason':'SCRAPINGANT_API_KEY missing'}));return 2
    start=time.monotonic()
    result={'target':URL,'browser':True,'proxy_type':'datacenter','tested_at':datetime.now(timezone.utc).isoformat(),'server_acceptance_tested':False}
    try:
        response=requests.get('https://api.scrapingant.com/v2/general',params={'url':URL,'browser':'true','proxy_type':'datacenter','x-api-key':key},timeout=90)
        body=response.text
        safe=body.replace(key,'[REDACTED]')
        # Remove potential CAPTCHA response tokens and session widget URLs from the archived HTML.
        safe=re.sub(r'(<textarea\b[^>]*name="g-recaptcha-response"[^>]*>).*?(</textarea>)',r'\1[REDACTED RESPONSE]\2',safe,flags=re.S)
        safe=re.sub(r'(<iframe\b[^>]*src=")[^"]*(")',r'\1[REDACTED WIDGET URL]\2',safe)
        Path('expected_output/scrapingant-response.redacted.html').write_text(safe)
        token=re.search(r'<textarea\b[^>]*name="g-recaptcha-response"[^>]*>(.*?)</textarea>',body,re.S)
        result.update(api_http_status=response.status_code,target_http_status=response.headers.get('Ant-page-status-code'),credits_cost=response.headers.get('Ant-credits-cost'),response_bytes=len(response.content),raw_sha256=hashlib.sha256(response.content).hexdigest(),widget_present='g-recaptcha' in body,token_length=len(token.group(1)) if token else None,success_message_present='Verification Success' in body)
        result['outcome']='html_returned' if response.ok else 'api_error'
    except requests.RequestException as exc:
        result.update(outcome='transport_error',error=type(exc).__name__)
    result['elapsed_seconds']=round(time.monotonic()-start,2);print(json.dumps(result,indent=2))
    return 0 if result.get('api_http_status')==200 else 1
if __name__=='__main__': raise SystemExit(main())
