"""Observe the returned CAPTCHA demo, without equating fetched HTML to a solve."""
import hashlib,json,os,time
from datetime import datetime,timezone
from html.parser import HTMLParser
import requests

class TokenMetadata(HTMLParser):
    def __init__(self):
        super().__init__();self.in_token=False;self.token_length=None;self.widget_present=False
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if 'g-recaptcha' in attrs.get('class','').split(): self.widget_present=True
        if tag=='textarea' and attrs.get('name')=='g-recaptcha-response':
            self.in_token=True;self.token_length=0
    def handle_data(self, data):
        if self.in_token: self.token_length+=len(data)
    def handle_endtag(self, tag):
        if tag=='textarea': self.in_token=False

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
        metadata=TokenMetadata();metadata.feed(body)
        result.update(api_http_status=response.status_code,target_http_status=response.headers.get('Ant-page-status-code'),credits_cost=response.headers.get('Ant-credits-cost'),response_bytes=len(response.content),raw_sha256=hashlib.sha256(response.content).hexdigest(),widget_present=metadata.widget_present,token_length=metadata.token_length,success_message_present='Verification Success' in body)
        result['outcome']='html_returned' if response.ok else 'api_error'
    except requests.RequestException as exc:
        result.update(outcome='transport_error',error=type(exc).__name__)
    result['elapsed_seconds']=round(time.monotonic()-start,2);print(json.dumps(result,indent=2))
    return 0 if result.get('api_http_status')==200 else 1
if __name__=='__main__': raise SystemExit(main())
