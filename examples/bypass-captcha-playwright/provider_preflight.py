"""Validate installed public SDK interfaces; never invent a live service result."""
import importlib.metadata as metadata
import inspect,json,os
from twocaptcha import TwoCaptcha, AsyncTwoCaptcha
from anticaptchaofficial.recaptchav2proxyless import recaptchaV2Proxyless
import capsolver

SPECS={
 '2captcha': ('2captcha-python','TWOCAPTCHA_API_KEY', TwoCaptcha, 'recaptcha'),
 'anticaptcha': ('anticaptchaofficial','ANTICAPTCHA_API_KEY',recaptchaV2Proxyless,'solve_and_return_solution'),
 'capsolver': ('capsolver','CAPSOLVER_API_KEY',capsolver,'solve'),
}
def main(provider):
    package,env,owner,method=SPECS[provider]
    api=getattr(owner,method)
    result={'provider':provider,'package':package,'version':metadata.version(package),'import_ok':True,'method':method,'signature':str(inspect.signature(api)),'credential_present':bool(os.environ.get(env)),'credential_variable':env,'paid_tasks_created':0,'solve_outcome':'not_run'}
    if provider=='2captcha':result['official_async_client_present']=hasattr(AsyncTwoCaptcha,'recaptcha')
    result['reason']='Live paid comparison requires a funded key, a bounded task budget and server acceptance measurement.' if result['credential_present'] else 'Missing funded credentials; package/interface check only.'
    print(json.dumps(result,indent=2))
    return 0
