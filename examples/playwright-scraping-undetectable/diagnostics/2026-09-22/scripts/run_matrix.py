"""Sequential, bounded research run; installation is separate. Never changes captured results silently."""
import argparse,json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--approaches',nargs='+',default=['chrome-control','patchright','python-stealth','extra-stealth','rebrowser','firefox-control','camoufox']);p.add_argument('--modes',nargs='+',default=['headless','headed']);p.add_argument('--repetitions',nargs='+',type=int,default=[1,2]);args=p.parse_args()
for rep in args.repetitions:
 for mode in args.modes:
  # Alternate order on second repeat, reducing systematic time/order bias (not a randomized trial).
  for approach in args.approaches if rep==1 else reversed(args.approaches):
   key=f'{approach}-{mode}-{rep}'
   if (ROOT/'results'/f'{key}.json').exists():raise SystemExit(f'Refusing to overwrite {key}; move/remove explicitly before rerun')
   if approach in ['extra-stealth','rebrowser']:cmd=['node',str(ROOT/'node/probe.cjs')]
   else:cmd=[os.environ.get('CAMOUFOX_PYTHON','/tmp/camoufox-research-venv/bin/python') if approach in ['camoufox','firefox-control'] else os.environ.get('PLAYWRIGHT_PYTHON','/tmp/pw-research-venv/bin/python'),str(ROOT/'scripts/probe.py')]
   cmd += [approach,mode,str(rep)]; print('$ '+' '.join(cmd),flush=True)
   child=subprocess.Popen(cmd,cwd=ROOT,start_new_session=True)
   try:code=child.wait(timeout=180)
   except subprocess.TimeoutExpired:
    os.killpg(child.pid,signal.SIGTERM);child.wait(timeout=10);code=124
    if not (ROOT/'results'/f'{key}.json').exists():(ROOT/'results'/f'{key}.json').write_text(json.dumps({'key':key,'approach':approach,'mode':mode,'repetition':rep,'launch_error':'Harness process exceeded180seconds; no verdict','pages':[]},indent=2)+'\n')
   print(f'exit={code}',flush=True);time.sleep(1)
